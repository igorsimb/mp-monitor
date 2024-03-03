import decimal
import logging
import random
import re
import time
from typing import Any

import httpx
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import Page
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from django_celery_beat.models import PeriodicTask
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from main.exceptions import InvalidSKUException
from main.models import Item, Tenant

logger = logging.getLogger(__name__)

MAX_RETRIES = 10
MAX_ITEMS_ON_SCREEN = 10
User = get_user_model()


def scrape_live_price(sku):
    """Scrapes the live price of a product from Wildberries.

    Args:
        sku (str): The SKU of the product.

    Returns:
        int: The live price of the product.
    """
    logger.info("Starting to scrape live price")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    # chrome_options.add_argument("--no-sandbox")
    # chrome_options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=chrome_options)
    # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    regular_link = f"https://www.wildberries.ru/catalog/{sku}/detail.aspx"
    driver.get(regular_link)
    # Wait for the presence of the price element
    try:
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located(
                (
                    By.XPATH,
                    (
                        "//div[@class='product-page__price-block product-page__price-block--aside']//ins["
                        "@class='price-block__final-price']"
                    ),
                )
            )
        )
    except TimeoutException:
        price_element = None

    if price_element is not None:
        parsed_price = (
            price_element.get_attribute("textContent")
            .replace("₽", "")
            .replace("\xa0", "")
            .strip()
        )
        parsed_price = int(parsed_price)
        print(f"My final price ee: {parsed_price} ({type(parsed_price)})")
    else:
        parsed_price = 0
        print("Parsed price is ZERO")

    return parsed_price


def extract_price_before_spp_old(item: dict) -> float | None:
    try:
        sale_price = item["extended"]["basicPriceU"]
        logger.info("Found sale price in item['extended']['basicPriceU']")
    except KeyError:
        sale_price = item["priceU"]
        logger.info("Found sale price in item['priceU']")

    if sale_price is not None and isinstance(sale_price, (int, float)):
        try:
            seller_price = float(sale_price) / 100
        except (ValueError, TypeError):
            seller_price = None
    else:
        seller_price = None
    return seller_price


def extract_price_before_spp(item: dict) -> float | None:
    original_price = item["priceU"]
    sale = item["sale"]
    try:
        discount = original_price * (int(sale) / 100)
        price_before_spp = original_price - discount
        logger.info("Price before SPP = %s", price_before_spp)
        return float(price_before_spp) / 100
    except (KeyError, TypeError):
        logger.error("Could not extract price before SPP from item: %s", item)
        return None


def check_item_stock(item: dict) -> bool:
    sku = item.get("id")
    # Item availability is hidden in item.sizes[0].stocks
    is_in_stock = any(item["stocks"] for item in item.get("sizes", []))

    if is_in_stock:
        logger.info("At least one item for sku (%s) is in stock.", sku)
    else:
        logger.info("No items for sku (%s) are in stock.", sku)

    return is_in_stock


def is_sku_format_valid(sku: str) -> bool:
    """Check if the SKU has a valid format.

    Args:
        sku (str): The SKU to check.

    Returns:
        bool: True if the SKU is valid, False otherwise.
    """
    # only numbers, between 5-12 characters long
    if re.match(r"^[0-9]{5,12}$", sku):
        return True
    else:
        return False


def is_item_exists(item_info: list) -> bool:
    """Check if item exists on Wildberries.

    Non-existing items return an empty list.
    """
    if item_info:
        return True
    return False


# WB's API constantly changes. Right now:
#   no "extended" field in API
#   priceU = the price before every discount (scratched out)
#   sale = seller discount
#   salePriceU = the final price (aka, price with spp, no need for Selenium here)
def scrape_item(sku: str, use_selenium: bool = False) -> dict:
    """
    Scrape item from WB's API.

    Args:
        sku (str): The SKU of the product.
        use_selenium (bool): Whether to use Selenium to scrape the live price (slower).

    Returns:
        dict: A dictionary containing the data for the scraped item.
    """

    if not is_sku_format_valid(sku):
        logger.error("Invalid format for SKU: %s", sku)
        raise InvalidSKUException(message="Invalid format for SKU.", sku=sku)

    if use_selenium:
        logger.info("Going to scrape live for sku: %s", sku)
        price_after_spp = scrape_live_price(sku)
        logger.info("Live price: %s", price_after_spp)

    # Looks like this: https://card.wb.ru/cards/detail?appType=1&curr=rub&dest=-455203&nm={sku}
    url = httpx.URL(
        "https://card.wb.ru/cards/detail",
        params={"appType": 1, "curr": "rub", "dest": -455203, "nm": sku},
    )
    # pylint: disable=line-too-long
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0"
            " Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Origin": "https://www.wildberries.ru",
    }
    retry_count = 0
    data = {}

    logger.info("Starting while loop...")
    # in case of a server error, retry the request up to MAX_RETRIES times
    while retry_count < MAX_RETRIES:
        try:
            response = httpx.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            data = response.json()
            if data:
                logger.info("Breaking the loop...")
                break
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error occurred: %s. Failed to scrape url: %s. Attempt #%s",
                e,
                url,
                retry_count + 1,
            )
            retry_count += 1
            sleep_amount_sec = random.uniform(0.5, 5)
            logger.info("Sleeping for %s seconds", sleep_amount_sec)
            time.sleep(sleep_amount_sec)
    logger.info("Exited while loop...")

    item_info: list = data.get("data", {}).get("products")
    if not is_item_exists(item_info):
        raise InvalidSKUException(message="Request returned no item for SKU.", sku=sku)

    item = data.get("data", {}).get("products")[0]

    # makes sure that the correct id (i.e. = sku) is being pulled from api
    if item.get("id") != sku:
        for product in data.get("data", {}).get("products"):
            if product.get("id") == sku:
                item = product
                logger.info("Found item with SKU: %s", sku)
                break

    name = item.get("name")
    sku = item.get("id")
    # price with only seller discount
    price_before_spp = extract_price_before_spp(item)
    price_after_spp = item.get("salePriceU") / 100
    image = item.get("image")
    category = item.get("category")
    brand = item.get("brand")
    seller_name = item.get("brand")
    rating = float(item.get("rating")) if item.get("rating") is not None else None
    num_reviews = (
        int(item.get("feedbacks")) if item.get("feedbacks") is not None else None
    )

    logger.info("seller_price: %s", price_before_spp)
    if price_before_spp is None:
        logger.error("Could not find seller's price for sku %s", sku)

    logger.info("Checking if item is in stock")
    is_in_stock = check_item_stock(item)

    price_before_any_discount = (
        item.get("priceU") / 100
        if (item.get("priceU") and isinstance(item.get("priceU"), int))
        else None
    )

    try:
        seller_discount = item["extended"]["basicSale"]
    except KeyError:
        seller_discount = item["sale"]

    try:
        spp = round(((price_before_spp - price_after_spp) / price_before_spp) * 100)
    except TypeError:
        logger.error(
            "Could not calculate SPP for sku %s using price_before_spp (%s) and price_after_spp (%s)",
            sku,
            price_before_spp,
            price_after_spp,
        )
        spp = 0

    # breakdown of all types of prices and SPP (SPP currently is incorrect)
    logger.info("Price before any discount: %s", price_before_any_discount)
    logger.info("Seller's discount: %s", seller_discount)
    logger.info("Seller's price: %s", price_before_spp)
    logger.info("SPP: %s%%", spp)  # e.g. SPP: 5%
    logger.info("Live price on WB: %s", price_after_spp)

    return {
        "name": name,
        "sku": sku,
        "seller_price": price_before_spp,
        "price": price_after_spp,
        "spp": spp,
        "image": image,
        "category": category,
        "brand": brand,
        "seller_name": seller_name,
        "rating": rating,
        "num_reviews": num_reviews,
        "is_in_stock": is_in_stock,
    }


def scrape_items_from_skus(
    skus: str, is_parser_active: bool = False
) -> tuple[list[dict[str, Any]], list[str]]:
    """Scrapes item data from a string of SKUs.

    Args:
        skus: A string containing SKUs, separated by spaces, newlines, or commas.

    Returns a tuple consisting of:
        - A list of dictionaries, where each dictionary contains the data for a single item.
        - A list with invalid SKUs
    """
    logger.info("Going to scrape items: %s", skus)
    items_data = []
    invalid_skus = []
    for sku in re.split(r"\s+|\n|,(?:\s*)", skus):
        logger.info("Scraping item: %s", sku)
        try:
            item_data = scrape_item(sku)
            items_data.append(item_data)
            if is_parser_active:
                item_data["is_parser_active"] = True
        except InvalidSKUException as e:
            invalid_skus.append(e.sku)
    return items_data, invalid_skus


def update_or_create_items(request, items_data):
    logger.info("Update request=%s", request)
    for item_data in items_data:
        item, created = Item.objects.update_or_create(  # pylint: disable=unused-variable
            tenant=request.user.tenant,
            sku=item_data["sku"],
            defaults=item_data,
        )


# TODO: this should be just update, not update_or_create
def update_or_create_items_interval(tenant_id, items_data):
    logger.info("Update tenant_id=%s", tenant_id)
    tenant = Tenant.objects.get(id=tenant_id)
    logger.info("Update tenant=%s", tenant)
    for item_data in items_data:
        item, created = Item.objects.update_or_create(  # pylint: disable=unused-variable
            tenant=tenant,
            sku=item_data["sku"],
            defaults=item_data,
        )


def is_at_least_one_item_selected(
    request: HttpRequest, selected_item_ids: list[str] | str
) -> bool:
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
    logger.info("All boxes unchecked.")


def show_successful_scrape_message(
    request: HttpRequest,
    items_data: list[dict],
    max_items_on_screen: int = MAX_ITEMS_ON_SCREEN,
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
        messages.error(request, "Добавьте хотя бы 1 товар с корректным артикулом")
        return
    if len(items_data) == 1:
        # pylint: disable=inconsistent-quotes
        # debug, info, success, warning, error
        messages.success(
            request,
            f'Обновлена информация по товару: "{items_data[0]["name"]} ({items_data[0]["sku"]})"',
        )
    elif 1 < len(items_data) <= max_items_on_screen:
        formatted_items = [
            f"<li>{item['sku']}: {item['name']}</li>" for item in items_data
        ]
        messages.success(
            request,
            mark_safe(
                f'Обновлена информация по товарам: <ul>{"".join(formatted_items)}</ul>'
            ),
        )
    elif len(items_data) > max_items_on_screen:
        messages.success(request, f"Обновлена информация по {len(items_data)} товарам")


def show_invalid_skus_message(request: HttpRequest, invalid_skus: list) -> None:
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


def calculate_percentage_change(prices: Page) -> None:
    """Calculate the percentage change for a list of prices.

    This function computes the percentage change of prices and attaches
    the calculated values to the 'percent_change' attribute of each Price object
    in the 'prices' list.

    Args:
        prices (list): A list of Price objects to calculate the percentage change for.

    Returns:
        None: The function modifies the 'percent_change' attribute of each Price object in place.

    Notes:
        - If there are no previous prices to compare, 'percent_change' is set to 0.
        - If a TypeError occurs while comparing prices, a warning message is logged.

    Example of use in item_detail.html template:
        {% for price in prices %}
            {{ price.percent_change|floatformat}}%
        {% endfor %}
    """
    for i in range(len(prices)):
        try:
            # if i == 0:
            #     prices[i].percent_change = 0  # No previous price to compare to
            # else:
            previous_price = prices[i + 1].value
            current_price = prices[i].value
            percent_change = ((current_price - previous_price) / previous_price) * 100
            prices[i].percent_change = round(percent_change, 2)
        except IndexError:
            prices[i].percent_change = 0
        except TypeError:
            logger.warning("Can't compare price to NoneType")
            prices[i].percent_change = 100
        except decimal.DivisionByZero:
            logger.warning("Can't divide by zero")
            prices[i].percent_change = 100


def add_table_class(prices: Page) -> None:
    """Add Bootstrap table classes based on price comparison.

    Iterates through a list of Price objects and assigns the appropriate
    Bootstrap table classes('table_class' attribute) based on price comparisons.

    Args:
        prices (list): A list of Price objects to assign table classes to.

    Returns:
        None: The function modifies the 'table_class' attribute of each Price object in place.

    Example of use in a template:
         {% for price in prices %}
             <tr class="{{ price.table_class }}">
                 <td>...</td>
             </tr>
         {% endfor %}

    See Also:
        - https://getbootstrap.com/docs/5.3/content/tables/#variants

    """
    for i in range(len(prices)):
        try:
            if prices[i].value < prices[i + 1].value:
                prices[i].table_class = "table-danger"
            elif prices[i].value > prices[i + 1].value:
                prices[i].table_class = "table-success"
            else:
                prices[i].table_class = ""

        # the original price is the last price in the list, so no comparison is possible
        except IndexError:
            prices[i].table_class = ""
        except TypeError:
            logger.warning("Can't compare price to NoneType")


def add_price_trend_indicator(prices: Page) -> None:
    """Add trend indicators to a list of Price objects based on price comparison.

    Iterates through a list of Price objects and assigns trend indicators
    ('trend' attribute) based on price comparisons.

    Example of use in a template:
        {% for price in prices %}
            <tr>
                <td>{{ price.trend }}</td>
                ...
            </tr>
        {% endfor %}
    """
    for i in range(len(prices)):
        try:
            if prices[i].value < prices[i + 1].value:
                prices[i].trend = "↓"
            elif prices[i].value > prices[i + 1].value:
                prices[i].trend = "↑"
            else:
                prices[i].trend = ""

        # the original price is the last price in the list, so no comparison is possible
        except IndexError:
            prices[i].table_class = ""
        except TypeError:
            logger.warning("Can't compare price to NoneType")


def periodic_task_exists(request: WSGIRequest) -> bool:
    """Checks for the existence of a periodic task with the given name."""

    try:
        PeriodicTask.objects.get(name=f"scrape_interval_task_{request.username}")
        return True
    except PeriodicTask.DoesNotExist:
        return False
