"""
User feedback system utilities for displaying messages and processing notifications.
"""

import logging
from typing import Any, Dict, List

from django.contrib import messages
from django.db.models import Q
from django.http import HttpRequest
from django.utils.safestring import mark_safe

import config
from accounts.models import Tenant
from main.models import Item
from notifier.models import PriceAlert
from notifier.tasks import send_price_change_email
from utils import items

logger = logging.getLogger(__name__)


def show_successful_scrape_message(
    request: HttpRequest, items_data: List[Dict[str, Any]], max_items_on_screen=config.MAX_ITEMS_ON_SCREEN
) -> None:
    if not items_data:
        messages.error(request, "Добавьте хотя бы 1 товар с корректным артикулом")
        return

    if len(items_data) == 1:
        messages.success(
            request,
            f'Обновлена информация по товару: "{items_data[0]["name"]} ({items_data[0]["sku"]})"',
        )
    elif 1 < len(items_data) <= max_items_on_screen:
        formatted_items = [f"<li>{item['sku']}: {item['name']}</li>" for item in items_data]
        messages.success(
            request,
            mark_safe(f'Обновлена информация по товарам: <ul>{"".join(formatted_items)}</ul>'),
        )
    elif len(items_data) > max_items_on_screen:
        messages.success(request, f"Обновлена информация по {len(items_data)} товарам")


def show_invalid_skus_message(request: HttpRequest, invalid_skus: list) -> None:
    if len(invalid_skus) == 1:
        messages.warning(
            request,
            f"Не удалось добавить следующий артикул: {', '.join(invalid_skus)}<br>"
            "Возможен неверный формат артикула.",
        )
    else:
        messages.warning(
            request,
            f"Не удалось добавить следующие артикулы: {', '.join(invalid_skus)}<br>"
            "Возможен неверный формат артикулов.",
        )


def deactivate_price_alerts(tenant: Tenant, items_with_active_alerts: list[Item]) -> None:
    """
    Once price alerts are sent, deactivate them to prevent sending them again.
    """
    for item in items_with_active_alerts:
        current_price = item.price

        # Get alerts for this item and tenant
        alerts = PriceAlert.objects.filter(tenant=tenant, items=item)

        # Filter alerts based on the trigger condition
        triggered_alerts = alerts.filter(
            Q(target_price_direction=PriceAlert.TargetPriceDirection.UP, target_price__lte=current_price)
            | Q(target_price_direction=PriceAlert.TargetPriceDirection.DOWN, target_price__gte=current_price)
        ).filter(is_active=True)

        triggered_alerts.update(is_active=False)


def delete_price_alerts(tenant: Tenant, items_with_active_alerts: list[Item]) -> None:
    """
    Once price alerts are sent, delete them to remove triggered alerts.
    """
    for item in items_with_active_alerts:
        current_price = item.price

        # Get alerts for this item and tenant
        alerts = PriceAlert.objects.filter(tenant=tenant, items=item)

        # Filter alerts based on the trigger condition
        triggered_alerts = alerts.filter(
            Q(target_price_direction=PriceAlert.TargetPriceDirection.UP, target_price__lte=current_price)
            | Q(target_price_direction=PriceAlert.TargetPriceDirection.DOWN, target_price__gte=current_price)
        ).filter(is_active=True)

        triggered_alerts.delete()


def process_price_change_notifications(tenant: Tenant, items_data: list[dict]) -> None:
    logger.info("Checking is user needs to be notified of price changes...")

    # Step 1
    items_with_price_change: list[Item] = items.get_items_with_price_change(tenant, items_data)

    # Step 2
    items_with_active_alerts: list[Item] = items.get_items_with_active_alerts(tenant, items_with_price_change)

    # Step 3
    send_price_change_email(tenant, items_with_active_alerts)

    # Step 4
    delete_price_alerts(tenant, items_with_active_alerts)
    # deactivate_price_alerts(tenant, items_with_active_alerts)
