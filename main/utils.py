import logging

import httpx

from main.models import Item

logger = logging.getLogger(__name__)

MAX_RETRIES = 3

def get_price(item: dict) -> float | None:
    """
    Extracts and coverts the price of an item and makes sure it's in the correct format.
    Otherwise, returns None
    """
    sale_price = item.get("salePriceU")

    if sale_price is not None and isinstance(sale_price, (int, float)):
        try:
            price = float(sale_price) / 100
        except (ValueError, TypeError):
            price = None
    else:
        price = None
    return price


def scrape_item(sku):
    # https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={sku}
    url = httpx.URL("https://card.wb.ru/cards/detail", params={'appType': 1, 'curr': 'rub', 'nm': sku})
    retry_count = 0
    data = {}

    # in case of a server error, retry the request up to 3 times
    while retry_count < MAX_RETRIES:
        try:
            response = httpx.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            break
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            retry_count += 1

    item = data.get("data", {}).get("products")[0]

    name = item.get("name")
    sku = item.get("id")
    price = get_price(item)
    image = item.get("image")
    category = item.get("category")
    brand = item.get("brand")
    seller_name = item.get("brand")
    rating = float(item.get("rating")) if item.get("rating") is not None else None
    num_reviews = int(item.get("feedbacks")) if item.get("feedbacks") is not None else None

    if price is None:
        logger.error(f"Could not find salePriceU for sku {sku}")

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


def uncheck_all_boxes(request):
    Item.objects.filter(tenant=request.user.tenant.id).update(parser_active=False)
