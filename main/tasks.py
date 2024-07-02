import logging

from celery import shared_task
from django.contrib import messages
from django.contrib.auth import get_user_model
from django_celery_beat.models import PeriodicTask

from accounts.models import Tenant
from .exceptions import QuotaExceededException
from .models import Item
from .utils import (
    scrape_item,
    scrape_items_from_skus,
    update_or_create_items_interval,
    update_user_quota_for_allowed_parse_units,
)

logger = logging.getLogger(__name__)
user = get_user_model()


# Currently not used, see: https://github.com/igorsimb/mp-monitor/issues/114
@shared_task(bind=True)
def scrape_interval_task(self, tenant_id: int, selected_item_ids: list[int]) -> None:  # pylint: disable=[unused-argument]
    items = Item.objects.filter(id__in=selected_item_ids)
    logger.info("Found items: %s. Selected Item ids: %s", items, selected_item_ids)
    tenant = Tenant.objects.get(id=tenant_id)
    logger.info("Tenant found: %s", tenant)
    items_skus = [item.sku for item in items]
    logger.info("Items SKUs found: %s", items_skus)

    items_data = []

    for sku in items_skus:
        item_data = scrape_item(sku)
        items_data.append(item_data)

    logger.info("Items data: %s", items_data)

    for item_data in items_data:
        logger.info(
            "Looking for item with SKU: %s | Name: %s...",
            item_data["sku"],
            item_data["name"],
        )
        item, created = Item.objects.update_or_create(
            tenant=tenant,
            sku=item_data["sku"],
            defaults=item_data,
        )
        if created:
            logger.debug("Created item: %s | Name: %s...", item.sku, item.name)
        else:
            logger.debug("Updated item: %s | Name: %s...", item.sku, item.name)


@shared_task(bind=True)
def update_or_create_items_task(self, tenant_id, skus_list):
    def convert_list_to_string(input_list):
        # input: [179081012, 180771445, 155282898]
        # output: '179081012,180771445,155282898'
        if not input_list:
            return ""
        return ",".join([str(integer) for integer in input_list])

    user_to_update = user.objects.get(tenant__id=tenant_id)
    if user_to_update.is_demo_user:
        try:
            # update_user_quota_for_scheduled_updates(user_to_update)
            update_user_quota_for_allowed_parse_units(user_to_update, skus_list)
        except QuotaExceededException as e:
            logger.warning(e.message)
            return

    skus = convert_list_to_string(skus_list)
    # scrape_items_from_skus returns a tuple, but only the first part is needed for update_or_create_items_interval
    items_data, _ = scrape_items_from_skus(skus, is_parser_active=True)
    update_or_create_items_interval(tenant_id, items_data)

    task_name = self.request.properties["periodic_task_name"]
    task_obj = PeriodicTask.objects.get(name=task_name)
    if not task_obj:
        logger.error("Task with name %s not found.", task_name)
        messages.error(self.request, "Расписание не найдено. Попробуйте еще раз или обратитесь в службу поддержки.")
        return

    task_obj.save()
