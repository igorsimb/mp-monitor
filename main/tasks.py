import datetime

from celery import shared_task
from celery.beat import logger
from .models import Printer, Item, Price
from .scrape import get_scraped_data


@shared_task(schedule=datetime.timedelta(seconds=10)) # does not work
def print_hello():
    logger.info(f'LOGGER Hello, current time is {datetime.datetime.now()}')


# @shared_task
# def print_task():
#     current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     printer = Printer.objects.create(name="printer")
#     printer.save()
#     print(f"Task executed at : {current_time}")


@shared_task
def print_task():
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    printer = Printer.objects.create(name="printer")
    printer.save()
    print(f"Task executed at : {current_time}")


@shared_task(bind=True)
def scrape_interval_task_old(self, tenant): # probably don't need the 'self'
# def scrape_interval_task():
    items = Item.objects.filter(tenant=tenant)
    print(f"{self.name=}")
    # items = Item.objects.all()
    for index, item in enumerate(items, start=1):
        print(f"{index}. {item}")
        # item, created = Item.objects.update_or_create(
        #     tenant=request.user.tenant,
        #     sku=item_data["sku"],
        #     defaults=item_data,
        # )
        # price = Price.objects.create()
        # price.save()


@shared_task(bind=True)
def scrape_interval_task(self, tenant):  # probably don't need the 'self'
    # def scrape_interval_task():
    #     items = Item.objects.filter(tenant=tenant)
    #     print(f"{self.name=}")
    # items = Item.objects.all()
    # for index, item in enumerate(items, start=1):
    #     print(f"{index}. {item}")

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
        print(f"{item} updated")

    # item, created = Item.objects.update_or_create(
    #     tenant=request.user.tenant,
    #     sku=item_data["sku"],
    #     defaults=item_data,
    # )
    # price = Price.objects.create()
    # price.save()