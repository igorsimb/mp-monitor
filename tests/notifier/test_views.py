import logging

from django.test import Client
from django.urls import reverse
from pytest_django.asserts import assertTemplateUsed

from notifier.models import PriceAlert
from tests.factories import ItemFactory, UserFactory, PriceAlertFactory

client = Client()
logger = logging.getLogger(__name__)


def test_create_price_alert() -> None:
    user = UserFactory()
    tenant = user.tenant
    client.force_login(user)
    item = ItemFactory(tenant=tenant)
    logger.info("Creating a price alert for item %s", item)
    alert = PriceAlertFactory(tenant=tenant, items=item)
    alerts_count = PriceAlert.objects.filter(tenant=tenant).count()
    logger.info("Price alerts count before POST request: %s", alerts_count)

    logger.info("Sending a POST request to create a price alert for item %s", item)
    headers = {"HTTP_HX_REQUEST": "true"}
    response = client.post(
        reverse("create_price_alert", args=[item.id]),
        data={"target_price": alert.target_price, "message": alert.message},
        **headers,
    )
    new_count = PriceAlert.objects.filter(tenant=tenant).count()
    logger.info("Price alerts count after POST request: %s", new_count)

    # assert the count is increased after the POST request
    assert new_count == alerts_count + 1

    assertTemplateUsed(response, "notifier/partials/alert_list.html")


def test_cannot_create_alert_with_negative_target_price() -> None:
    user = UserFactory()
    tenant = user.tenant
    client.force_login(user)
    item = ItemFactory(tenant=tenant)
    logger.info("Creating a price alert for item %s", item)
    alert = PriceAlertFactory(tenant=tenant, items=item)
    alerts_count = PriceAlert.objects.filter(tenant=tenant).count()
    logger.info("Price alerts count before POST request: %s", alerts_count)

    logger.info("Sending a POST request to create a price alert for item %s", item)
    headers = {"HTTP_HX_REQUEST": "true"}
    client.post(
        reverse("create_price_alert", args=[item.id]),
        data={"target_price": -100, "message": alert.message},
        **headers,
    )
    new_count = PriceAlert.objects.filter(tenant=tenant).count()
    logger.info("Price alerts count after POST request: %s", new_count)

    # assert the count did not increase after the POST request
    assert new_count == alerts_count


def test_update_price_alert() -> None:
    user = UserFactory()
    tenant = user.tenant
    client.force_login(user)
    item = ItemFactory(tenant=tenant)
    alert = PriceAlertFactory(tenant=tenant, items=item)
    alerts_count = PriceAlert.objects.filter(tenant=tenant).count()
    alert.items.add(item)

    old_target_price = alert.target_price
    old_message = alert.message

    new_target_price = alert.target_price + 100
    new_message = "Alert message updated"

    logger.info("Sending a POST request to update a price alert for item %s", item)
    client.post(
        reverse("edit_price_alert", kwargs={"alert_id": alert.id}),
        data={"target_price": new_target_price, "message": new_message},
    )

    alert.refresh_from_db()
    new_count = PriceAlert.objects.filter(tenant=tenant).count()

    # check that the alert was UPDATED, not created a new one
    assert new_count == alerts_count
    assert old_target_price != new_target_price
    assert alert.target_price == new_target_price
    assert old_message != new_message
    assert alert.message == new_message


def test_delete_price_alert() -> None:
    user = UserFactory()
    tenant = user.tenant
    client.force_login(user)
    item = ItemFactory(tenant=tenant)
    alert = PriceAlertFactory(tenant=tenant, items=item)

    old_alerts_count = PriceAlert.objects.filter(tenant=tenant).count()
    assert old_alerts_count == 1

    logger.info("Sending a DELETE request to delete a price alert for item %s", item)
    client.delete(
        reverse("delete_price_alert", kwargs={"alert_id": alert.id}),
    )

    new_alerts_count = PriceAlert.objects.filter(tenant=tenant).count()
    assert new_alerts_count == 0
