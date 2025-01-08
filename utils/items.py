"""Item state management and operations utilities."""

import logging
from typing import Any, Dict, List

from django.contrib import messages
from django.core.handlers.wsgi import WSGIRequest
from django.db.models import Q, Prefetch
from django.http import HttpRequest

from accounts.models import Tenant
from main.models import Item, Price
from notifier.models import PriceAlert

logger = logging.getLogger(__name__)


def update_or_create_items(request: HttpRequest, items_data: List[Dict[str, Any]]) -> None:
    """Update existing items or create new ones for the user's tenant.

    Args:
        request: The HTTP request object with user information.
        items_data: List of item data dictionaries.
    """
    logger.info("Update from user=%s", request.user.id if request.user.is_authenticated else "Anonymous")
    for item_data in items_data:
        item, created = Item.objects.update_or_create(  # pylint: disable=unused-variable
            tenant=request.user.tenant,
            sku=item_data["sku"],
            defaults=item_data,
        )


def update_or_create_items_interval(tenant_id, items_data):
    """Update or create items for a specific tenant.

    Args:
        tenant_id: ID of the tenant.
        items_data: List of item data dictionaries.
    """
    logger.info("Update tenant_id=%s", tenant_id)
    tenant = Tenant.objects.get(id=tenant_id)
    logger.info("Update tenant=%s", tenant)
    for item_data in items_data:
        item, created = Item.objects.update_or_create(  # pylint: disable=unused-variable
            tenant=tenant,
            sku=item_data["sku"],
            defaults=item_data,
        )


def is_at_least_one_item_selected(request: HttpRequest, selected_item_ids: list[str] | str) -> bool:
    """Check if at least one item is selected.

    Args:
        request: The HttpRequest object.
        selected_item_ids: A list of stringified integers representing the IDs of the selected items.

    Returns:
        True if at least one item is selected, False otherwise.
    """
    if not selected_item_ids:
        messages.error(request, "Выберите хотя бы 1 товар")
        logger.warning("No items were selected. Task not created.")
        return False

    logger.info("Items with these ids where selected: %s", selected_item_ids)
    return True


def uncheck_all_boxes(request: HttpRequest) -> None:
    """Uncheck all boxes in the item list page.

    Since HTML checkboxes don't inherently signal when unchecked,
    we uncheck everything so that later on an **updated** items list can be checked.

    Args:
        request: The HttpRequest object.
    """
    logger.info("Unchecking all boxes in the item list page.")
    Item.objects.filter(tenant=request.user.tenant.id).update(is_parser_active=False)  # type: ignore
    logger.info("All boxes unchecked.")


def activate_parsing_for_selected_items(request: WSGIRequest, skus_list: list[int]) -> None:
    """Activate parsing for the specified items.

    Args:
        request: The WSGIRequest object.
        skus_list: List of SKUs to activate parsing for.
    """
    Item.objects.filter(Q(tenant_id=request.user.tenant.id) & Q(sku__in=skus_list)).update(is_parser_active=True)


def get_items_with_price_changes_over_threshold(tenant: Tenant, items_data: list[dict]) -> list[Item]:
    """
    Check if any items have price change that is over the threshold set in the tenant settings.

    Args:
        tenant: The tenant whose items are being checked.
        items_data: List of dictionaries containing item data.

    Note:
        Uses tenant.price_change_threshold to determine price changes
    """

    # temporary limiting functionality to superusers
    if not tenant.users.filter(is_superuser=True).exists():
        logger.info("No superusers found. Exiting.")
        return []

    items_with_price_change: list[Item] = []
    items = Item.objects.filter(sku__in=[item["sku"] for item in items_data])  # Queryset[Item]

    logger.info("Checking if any items have price change...")
    for item in items:
        if item.previous_price and abs(item.price_percent_change) > tenant.price_change_threshold:
            items_with_price_change.append(item)

    logger.info("Found %s items with price change", len(items_with_price_change))
    return items_with_price_change


def get_items_with_price_change(tenant: Tenant, items_data: list[dict]) -> list[Item]:
    """
    Fetch items with price changes for the given tenant and items data.
    """
    items_with_price_change: list[Item] = []
    # Queryset[Item]
    items = Item.objects.filter(sku__in=[item["sku"] for item in items_data], tenant=tenant).prefetch_related(
        Prefetch("prices", queryset=Price.objects.order_by("-created_at"))
    )

    logger.info("Checking if any items have price change...")
    for item in items:
        if item.previous_price != item.price:
            items_with_price_change.append(item)

    return items_with_price_change


def get_items_with_active_alerts(tenant: Tenant, items_with_price_change: list[Item]) -> list[Item]:
    """
    Fetch items with active price alerts for the given tenant.
    Returns a list of items that hit the threshold to trigger the alert.
    """
    items_with_alerts = Item.objects.filter(id__in=[item.id for item in items_with_price_change]).prefetch_related(
        Prefetch(
            "price_alerts",
            queryset=PriceAlert.objects.filter(tenant=tenant, is_active=True),
            to_attr="active_price_alerts",
        )
    )

    def _alert_triggered(alert: PriceAlert, item: Item) -> bool:
        """
        Filter items that have at least one active alert triggered by price change
        The item's price change is compared to target_price and checks whether the new price hit the threshold
        (either UP or DOWN) set by user to trigger the alert
        """
        if alert.target_price_direction == PriceAlert.TargetPriceDirection.UP:
            return item.previous_price < alert.target_price <= item.current_price
        elif alert.target_price_direction == PriceAlert.TargetPriceDirection.DOWN:
            return item.previous_price > alert.target_price >= item.current_price
        return False

    # Filters only items where at least one alert is triggered.
    return [
        item for item in items_with_alerts if any(_alert_triggered(alert, item) for alert in item.active_price_alerts)
    ]

    # items_with_active_alerts: list = [item for item in items_with_alerts if item.active_price_alerts]
    # return items_with_active_alerts
