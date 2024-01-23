import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .models import Item, Tenant
from .utils import scrape_item, scrape_items_from_skus, update_or_create_items_interval

logger = logging.getLogger(__name__)
user = get_user_model()


@shared_task(bind=True)
def scrape_interval_task(self, tenant_id: int, selected_item_ids: list[int]) -> None: # pylint: disable=[unused-argument]
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
        logger.info("Looking for item with SKU: %s | Name: %s...", item_data["sku"], item_data["name"])
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

    skus = convert_list_to_string(skus_list)
    items_data = scrape_items_from_skus(skus, is_parser_active=True)
    update_or_create_items_interval(tenant_id, items_data)

