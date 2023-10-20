import logging
import re
from typing import Any

import httpx
from django.contrib import messages
from django.http import HttpRequest
from django.utils.safestring import mark_safe

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from main.models import Item

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
MAX_ITEMS_ON_SCREEN = 10


def scrape_live_price(sku):
    """Scrapes the live price of a product from Wildberries.

    Args:
        sku (str): The SKU of the product.

    Returns:
        int: The live price of the product.
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)

    regular_link = f"https://www.wildberries.ru/catalog/{sku}/detail.aspx"
    driver.get(regular_link)
    # Wait for the presence of the price element
    price_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located(
            (
                By.XPATH,
                "//div[@class='product-page__price-block product-page__price-block--aside']//ins["
                "@class='price-block__final-price']",
            )
        )
    )
    parsed_price = price_element.get_attribute("textContent").replace("₽", "").replace("\xa0", "").strip()
    parsed_price = int(parsed_price)
    print(f"My final price ee: {parsed_price} ({type(parsed_price)})")

    return parsed_price


def extract_valid_price(item: dict) -> float | None:
    sale_price = item["extended"]["basicPriceU"]

    if sale_price is not None and isinstance(sale_price, (int, float)):
        try:
            seller_price = float(sale_price) / 100
        except (ValueError, TypeError):
            seller_price = None
    else:
        seller_price = None
    return seller_price


def scrape_item(sku: str) -> dict:
    live_price = scrape_live_price(sku)
    logger.info("Live price: %s", live_price)
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

    # TODO: sometimes [0] is the wrong item. Need a checker that the item's SKU == sku (function's param)
    # If the item is not found, try to find the one with the correct sku. This will help avoid parsing the wrong item.
    item = data.get("data", {}).get("products")[0]
    logger.info("My Item: %s", item)

    name = item.get("name")
    sku = item.get("id")
    # price with only seller discount
    seller_price = extract_valid_price(item)
    image = item.get("image")
    category = item.get("category")
    brand = item.get("brand")
    seller_name = item.get("brand")
    rating = float(item.get("rating")) if item.get("rating") is not None else None
    num_reviews = int(item.get("feedbacks")) if item.get("feedbacks") is not None else None

    logger.info("seller_price: %s", seller_price)
    if seller_price is None:
        logger.error("Could not find salePriceU for sku %s", sku)

    price_before_any_discount = item.get("priceU") / 100 if item.get("priceU") else None
    seller_discount = item["extended"]["basicSale"]

    try:
        spp = round((seller_price - live_price) / seller_price * 100)
    except TypeError:
        logger.error(
            "Could not calculate SPP for sku %s using seller_price (%s) and live_price (%s)",
            sku,
            seller_price,
            live_price,
        )
        spp = 0

    # ! IMPORTANT: breakdown of all types of prices and SPP
    logger.info("Price before any discount: %s", price_before_any_discount)
    logger.info("Seller's discount: %s", seller_discount)
    logger.info("Seller's price: %s", seller_price)
    logger.info("SPP: %s%%", spp)  # e.g. SPP: 5%
    logger.info("Live price on WB: %s", live_price)

    return {
        "name": name,
        "sku": sku,
        "seller_price": seller_price,
        "price": live_price,
        "spp": spp,
        "image": image,
        "category": category,
        "brand": brand,
        "seller_name": seller_name,
        "rating": rating,
        "num_reviews": num_reviews,
    }


def scrape_items_from_skus(skus: str) -> list[dict[str, Any]]:
    """Scrapes item data from a string of SKUs.

    Args:
        skus: A string containing SKUs, separated by spaces, newlines, or commas.

    Returns:
        A list of dictionaries, where each dictionary contains the data for a single item.
    """
    logger.info("Going to scrape items: %s", skus)
    items_data = []
    for sku in re.split(r"\s+|\n|,(?:\s*)", skus):
        logger.info("Scraping item: %s", sku)
        item_data = scrape_item(sku)
        items_data.append(item_data)
    return items_data


def update_or_create_items(request, items_data):
    for item_data in items_data:
        item, created = Item.objects.update_or_create(  # pylint: disable=unused-variable
            tenant=request.user.tenant,
            sku=item_data["sku"],
            defaults=item_data,
        )


def is_at_least_one_item_selected(request: HttpRequest, selected_item_ids: list[str]) -> bool:
    """Checks if at least one item is selected.

    If not, displays an error message and redirects to the item list page.
    Args:
        request: The HttpRequest object.
        selected_item_ids: A list of stringified integers representing the IDs of the selected items.
    """
    if not selected_item_ids:
        messages.error(request, "Выберите хотя бы 1 товар")
        logger.warning("No items were selected. Task not created.")
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
    if not items_data:
        messages.error(request, "Добавьте хотя бы 1 товар")
        return
    if len(items_data) == 1:
        # pylint: disable=inconsistent-quotes
        # debug, info, success, warning, error
        messages.success(request, f'Обновлена информация по товару: "{items_data[0]["name"]} ({items_data[0]["sku"]})"')
    elif 1 < len(items_data) <= max_items_on_screen:
        formatted_items = [f"<li>{item['sku']}: {item['name']}</li>" for item in items_data]
        messages.success(request, mark_safe(f'Обновлена информация по товарам: <ul>{"".join(formatted_items)}</ul>'))
    elif len(items_data) > max_items_on_screen:
        messages.success(request, f"Обновлена информация по {len(items_data)} товарам")
