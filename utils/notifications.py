"""
User feedback system utilities for displaying messages and notifications.
"""

import logging
from typing import Any, Dict, List

from django.contrib import messages
from django.http import HttpRequest
from django.utils.safestring import mark_safe

import config

logger = logging.getLogger(__name__)


def show_successful_scrape_message(
    request: HttpRequest, items_data: List[Dict[str, Any]], max_items_on_screen=config.MAX_ITEMS_ON_SCREEN
) -> None:
    """Show success message after scraping items.

    Args:
        request: The HTTP request object.
        items_data: List of dictionaries containing item data.
        max_items_on_screen: Maximum number of items to show in the message.
    """
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
    """Show warning message for invalid SKUs.

    Args:
        request: The HTTP request object.
        invalid_skus: List of invalid SKUs.
    """
    if len(invalid_skus) == 1:
        messages.warning(
            request,
            f"Не удалось добавить следующий артикул: {', '.join(invalid_skus)}<br>"
            "Возможен неверный формат артикула, или товара с таким артикулом не существует. "
            "Пожалуйста, проверьте его корректность и при возникновении вопросов обратитесь в службу поддержки.",
        )
    else:
        messages.warning(
            request,
            f"Не удалось добавить следующие артикулы: {', '.join(invalid_skus)}<br>"
            "Возможен неверный формат артикулов, или товаров с такими артикулами не существует. "
            "Пожалуйста, проверьте их корректность и при возникновении вопросов обратитесь в службу поддержки.",
        )
