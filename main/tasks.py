import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from .models import Item, Tenant
from .utils import scrape_item

logger = logging.getLogger(__name__)
user = get_user_model()


@shared_task(bind=True)
def scrape_interval_task(self, tenant_id: int, selected_item_ids: list[int]) -> None: # pylint: disable=[unused-argument]
    items = Item.objects.filter(id__in=selected_item_ids)
    logger.info("Found items: %s", items)
    tenant = Tenant.objects.get(id=tenant_id)
    items_skus = [item.sku for item in items]

    items_data = []

    for sku in items_skus:
        item_data = scrape_item(sku)
        items_data.append(item_data)

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
