import logging

import httpx
from django.contrib import messages
from django.http import HttpRequest
from django.utils.safestring import mark_safe

from main.models import Item

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MAX_ITEMS_ON_SCREEN = 10


def extract_valid_price(item: dict) -> float | None:
    sale_price = item.get("salePriceU")

    if sale_price is not None and isinstance(sale_price, (int, float)):
        try:
            price = float(sale_price) / 100
        except (ValueError, TypeError):
            price = None
    else:
        price = None
    return price


def scrape_item(sku: str) -> dict:
    # Looks like this: https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={sku}
    url = httpx.URL("https://card.wb.ru/cards/detail", params={"appType": 1, "curr": "rub", "nm": sku})
    retry_count = 0
    data = {}

    # in case of a server error, retry the request up to MAX_RETRIES times
    while retry_count < MAX_RETRIES:
        try:
            response = httpx.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            break
        except httpx.HTTPError as e:
            logger.error("HTTP error occurred: %s", e)
            retry_count += 1

    item = data.get("data", {}).get("products")[0]

    name = item.get("name")
    sku = item.get("id")
    price = extract_valid_price(item)
    image = item.get("image")
    category = item.get("category")
    brand = item.get("brand")
    seller_name = item.get("brand")
    rating = float(item.get("rating")) if item.get("rating") is not None else None
    num_reviews = int(item.get("feedbacks")) if item.get("feedbacks") is not None else None

    if price is None:
        logger.error("Could not find salePriceU for sku %s", sku)

    return {
        "name": name,
        "sku": sku,
        "price": price,
        "image": image,
        "category": category,
        "brand": brand,
        "seller_name": seller_name,
        "rating": rating,
        "num_reviews": num_reviews,
    }


def at_least_one_item_selected(request: HttpRequest, selected_item_ids: list[str]) -> bool:
    """
    Checks if at least one item is selected.
    If not, displays an error message and redirects to the item list page.
    Args:
        request: The HttpRequest object.
        selected_item_ids: A list of stringified integers representing the IDs of the selected items.
    """
    if len(selected_item_ids) == 0:
        messages.error(request, "Выберите хотя бы 1 товар")
        logger.warning("No items were selected.")
        return False

    logger.info("Items with these ids where selected: %s", selected_item_ids)
    return True


def uncheck_all_boxes(request: HttpRequest) -> None:
    Item.objects.filter(tenant=request.user.tenant.id).update(is_parser_active=False)  # type: ignore
    logger.debug("All boxes unchecked.")


def show_successful_scrape_message(
    request: HttpRequest, items_data: list[dict], max_items_on_screen: int = MAX_ITEMS_ON_SCREEN
) -> None:
    """Displays a success message to the user indicating that the scrape was successful.
    Message depends on the number of items scraped to avoid screen clutter.

    Args:
        request: The HttpRequest object.
        items_data: A list of dictionaries containing the data for the scraped items.
        max_items_on_screen: The maximum number of items to display on the screen before it starts showing only
            the number of items.

    Returns:
        None
    """
    if len(items_data) == 0:
        messages.error(request, "Добавьте хотя бы 1 товар")
        return
    if len(items_data) == 1:
        # debug, info, success, warning, error
        messages.success(request, f'Обновлена информация по товару: "{items_data[0]["name"]} ({items_data[0]["sku"]})"')
    elif 1 < len(items_data) <= max_items_on_screen:
        formatted_items = [f"<li>{item['sku']}: {item['name']}</li>" for item in items_data]
        messages.success(request, mark_safe(f'Обновлена информация по товарам: <ul>{"".join(formatted_items)}</ul>'))
    elif len(items_data) > max_items_on_screen:
        messages.success(request, f"Обновлена информация по {len(items_data)} товарам")
