from celery import shared_task
from .models import Item
from .utils import get_scraped_data


@shared_task(bind=True)
def scrape_interval_task(self, tenant):

    items = Item.objects.filter(tenant=tenant)
    items_skus = [item.sku for item in items]
    items_data = []

    for sku in items_skus:
        item_data = get_scraped_data(sku)
        items_data.append(item_data)

    for item_data in items_data:
        item, created = Item.objects.update_or_create(
            tenant=tenant,
            sku=item_data["sku"],
            defaults=item_data,
        )