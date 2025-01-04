"""Item state management and operations utilities."""

import logging
from typing import Any, Dict, List

from django.contrib import messages
from django.core.handlers.wsgi import WSGIRequest
from django.db.models import Q
from django.http import HttpRequest

from accounts.models import Tenant
from main.models import Item

logger = logging.getLogger(__name__)


def update_or_create_items(request: HttpRequest, items_data: List[Dict[str, Any]]) -> None:
    """Update existing items or create new ones for the user's tenant.

    Args:
        request: The HTTP request object with user information.
        items_data: List of item data dictionaries.
    """
    logger.info("Update request=%s", request)
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
