"""
Core marketplace data fetching and validation utilities.
Currently, supports Wildberries marketplace with extensibility for future marketplaces.
"""

import logging
import re
import time
from typing import Any, Dict, Optional

import httpx
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from main.exceptions import InvalidSKUException

logger = logging.getLogger(__name__)


def is_sku_format_valid(sku: str) -> bool:
    """Check if the SKU has a valid format.

    Args:
        sku: The SKU to check.

    Returns:
        True if the SKU is valid, False otherwise.
    """
    # only numbers, between 5-12 characters long
    if re.match(r"^[0-9]{4,12}$", sku):
        return True
    else:
        return False


def is_item_exists(item_info: list) -> bool:
    """Check if item exists on Wildberries.

    Non-existing items return an empty list.

    Args:
        item_info: List containing item information from Wildberries API.

    Returns:
        True if item exists, False otherwise.
    """
    if item_info:
        return True
    return False


def scrape_live_price(sku: str) -> int:
    """Scrapes the live price of a product from Wildberries.

    Args:
        sku: The SKU of the product.

    Returns:
        The live price of the product.
    """
    logger.info("Starting to scrape live price")
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(options=chrome_options)

    regular_link = f"https://www.wildberries.ru/catalog/{sku}/detail.aspx"
    driver.get(regular_link)

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
        parsed_price = price_element.get_attribute("textContent").replace("₽", "").replace("\xa0", "").strip()
        parsed_price = int(parsed_price)
        print(f"My final price ee: {parsed_price} ({type(parsed_price)})")
    else:
        parsed_price = 0
        print("Parsed price is ZERO")

    return parsed_price


def extract_price_before_spp(item: dict) -> Optional[float]:
    """Extract price before SPP from item data.

    Args:
        item: Dictionary containing item data.

    Returns:
        Price before SPP or None if extraction fails.
    """
    sale = 0
    try:
        original_price = item["sizes"][0]["price"]["basic"]
        discount = original_price * (int(sale) / 100)
        price_before_spp = original_price - discount
        logger.info("Price before SPP = %s", price_before_spp)
        return float(price_before_spp) / 100
    except (KeyError, TypeError):
        logger.error("Could not extract price before SPP from item: %s", item)
        return None


def check_item_stock(item: dict) -> bool:
    """Check if item is in stock.

    Args:
        item: Dictionary containing item data.

    Returns:
        True if item is in stock, False otherwise.
    """
    sku = item.get("id")
    # Item availability is hidden in item.sizes[0].stocks
    is_in_stock = any(item["stocks"] for item in item.get("sizes", []))

    if is_in_stock:
        logger.info("At least one item for sku (%s) is in stock.", sku)
    else:
        logger.info("No items for sku (%s) are in stock.", sku)

    return is_in_stock


def scrape_item(sku: str, use_selenium: bool = False) -> Dict[str, Any]:
    """Scrape item from WB's API.

    Args:
        sku: The SKU of the product.
        use_selenium: Whether to use Selenium to scrape the live price (slower).

    Returns:
        A dictionary containing the data for the scraped item.

    Raises:
        InvalidSKUException: If the provided SKU is invalid
    """
    if not is_sku_format_valid(sku):
        logger.error("Invalid format for SKU: %s", sku)
        raise InvalidSKUException(message="Invalid format for SKU.", sku=sku)

    if use_selenium:
        logger.info("Going to scrape live for sku: %s", sku)
        price_after_spp = scrape_live_price(sku)
        logger.info("Live price: %s", price_after_spp)

    url = httpx.URL(
        "https://card.wb.ru/cards/v2/detail",
        params={"appType": 1, "curr": "rub", "dest": 123589330, "nm": sku},
    )

    headers = {  # noqa
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
        "Origin": "https://www.wildberries.ru",
    }
    retry_count = 0
    data = {}

    logger.info("Starting while loop...")
    while retry_count < config.MAX_RETRIES:
        try:
            response = httpx.get(url, timeout=60)
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
            sleep_amount_sec = min(60, 2**retry_count)
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
    price_before_spp = extract_price_before_spp(item) or 0
    logger.info("Checking if item is in stock")
    is_in_stock = check_item_stock(item)
    if is_in_stock:
        logger.info("Item with SKU %s is in stock. Checking price...", sku)
        price_after_spp = item["sizes"][0]["price"]["total"] / 100
    else:
        logger.info("Item is out of stock")
        price_after_spp = None
    image = item.get("image")
    category = item.get("category")
    brand = item.get("brand")
    seller_name = item.get("brand")
    rating = float(item.get("rating")) if item.get("rating") is not None else None
    num_reviews = int(item.get("feedbacks")) if item.get("feedbacks") is not None else None

    logger.info("seller_price: %s", price_before_spp)
    if price_before_spp is None:
        logger.error("Could not find seller's price for sku %s", sku)

    price_before_any_discount = (
        item.get("priceU") / 100 if (item.get("priceU") and isinstance(item.get("priceU"), int)) else None
    )

    try:
        seller_discount = item["extended"]["basicSale"]
    except KeyError:
        seller_discount = 0

    try:
        spp = round(((price_before_spp - price_after_spp) / price_before_spp) * 100)
    except TypeError as e:
        logger.error(
            "Could not calculate SPP for sku %s using price_before_spp (%s) and price_after_spp (%s). Error: %s",
            sku,
            price_before_spp,
            price_after_spp,
            e,
        )
        spp = 0
    except ZeroDivisionError:
        logger.error(
            "Could not calculate SPP. Division by zero occurred for sku %s using price_before_spp (%s) and"
            " price_after_spp (%s)",
            sku,
            price_before_spp,
            price_after_spp,
        )
        spp = None

    logger.info("Price before any discount: %s", price_before_any_discount)
    logger.info("Seller's discount: %s", seller_discount)
    logger.info("Seller's price: %s", price_before_spp)
    logger.info("SPP: %s%%", spp)
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


def scrape_items_from_skus(skus: str, is_parser_active: bool = False) -> tuple[list[dict[str, Any]], list[str]]:
    """Scrapes item data from a string of SKUs.

    Args:
        skus: A string containing SKUs, separated by spaces, newlines, or commas.
        is_parser_active: Whether the parser is active for these items.

    Returns:
        A tuple consisting of:
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
