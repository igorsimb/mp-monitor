import base64
import decimal
import hashlib
import logging
import re
import time
from typing import Any, List, Dict
from uuid import uuid4
import uuid
import httpx
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import Page
from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpRequest
from django.utils.safestring import mark_safe

# import this here if you encounter the following error:
# django.core.exceptions.ImproperlyConfigured: Requested setting USE_DEPRECATED_PYTZ, but settings are not configured.
# You must either define the environment variable DJANGO_SETTINGS_MODULE or call settings.configure() before accessing
# settings.
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mp_monitor.settings")
# django.setup()
from django_celery_beat.models import PeriodicTask
from selenium import webdriver
from selenium.common import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

import config
from accounts.models import TenantQuota, Tenant, PaymentPlan  # noqa
from main.exceptions import InvalidSKUException, QuotaExceededException, PlanScheduleLimitationException  # noqa
from main.models import Item, Payment, Order  # noqa

logger = logging.getLogger(__name__)

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
        parsed_price = price_element.get_attribute("textContent").replace("₽", "").replace("\xa0", "").strip()
        parsed_price = int(parsed_price)
        print(f"My final price ee: {parsed_price} ({type(parsed_price)})")
    else:
        parsed_price = 0
        print("Parsed price is ZERO")

    return parsed_price


def extract_price_before_spp(item: dict) -> float | None:
    # original_price = item["priceU"]
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
    if re.match(r"^[0-9]{4,12}$", sku):
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

    # Looks like this: https://card.wb.ru/cards/detail?appType=1&curr=rub&dest=-455203&nm={sku}
    url = httpx.URL(
        "https://card.wb.ru/cards/v2/detail",
        params={"appType": 1, "curr": "rub", "dest": 123589330, "nm": sku},
    )
    # pylint: disable=line-too-long

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
    # in case of a server error, retry the request up to MAX_RETRIES times
    # TODO: check if we can use a separate function connect() with a @retry decorator like so
    # https://github.com/federicoazzu/five_decorators/tree/main/decorators
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
            # using exponential backoff for HTTP requests to handle rate limits and network issues more gracefully
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
    # price with only seller discount
    price_before_spp = extract_price_before_spp(item) or 0
    # price_after_spp = item.get("salePriceU") / 100
    # data.products[2].sizes[0].price.total
    try:
        price_after_spp = item["sizes"][0]["price"]["total"] / 100
    except KeyError:
        price_after_spp = 0
    image = item.get("image")
    category = item.get("category")
    brand = item.get("brand")
    seller_name = item.get("brand")
    rating = float(item.get("rating")) if item.get("rating") is not None else None
    num_reviews = int(item.get("feedbacks")) if item.get("feedbacks") is not None else None

    logger.info("seller_price: %s", price_before_spp)
    if price_before_spp is None:
        logger.error("Could not find seller's price for sku %s", sku)

    logger.info("Checking if item is in stock")
    is_in_stock = check_item_stock(item)

    price_before_any_discount = (
        item.get("priceU") / 100 if (item.get("priceU") and isinstance(item.get("priceU"), int)) else None
    )

    try:
        seller_discount = item["extended"]["basicSale"]
    except KeyError:
        # seller_discount = item["sale"]
        seller_discount = 0

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
    except ZeroDivisionError:
        logger.error(
            "Could not calculate SPP. Division by zero occurred for sku %s using price_before_spp (%s) and"
            " price_after_spp (%s)",
            sku,
            price_before_spp,
            price_after_spp,
        )
        spp = None

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


def scrape_items_from_skus(skus: str, is_parser_active: bool = False) -> tuple[list[dict[str, Any]], list[str]]:
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
    # TODO: introduce sleep and improve UX: https://github.com/igorsimb/mp-monitor/issues/164
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


def update_or_create_items(request: HttpRequest, items_data: List[Dict[str, Any]]) -> None:
    """
    Update existing items or create new ones for the user's tenant.

    Args:
        request (HttpRequest): The HTTP request object with user information.
        items_data (List[Dict[str, Any]]): List of item data dictionaries.

    Returns:
        None
    """
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


def is_at_least_one_item_selected(request: HttpRequest, selected_item_ids: list[str] | str) -> bool:
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
    """Unchecks all boxes in the item list page.

    Since HTML checkboxes don't inherently signal when unchecked,
     we uncheck everything so that later on an **updated** items list can be checked
    """
    logger.info("Unchecking all boxes in the item list page.")
    Item.objects.filter(tenant=request.user.tenant.id).update(is_parser_active=False)  # type: ignore
    logger.info("All boxes unchecked.")


def activate_parsing_for_selected_items(request: WSGIRequest, skus_list: list[int]) -> None:
    """Activates parsing for the specified items by setting their `is_parser_active` field to True.
    Performs a single update operation to the database while making sure this operation is atomic and
    no other operations run while this is in progress.
    """
    Item.objects.filter(Q(tenant_id=request.user.tenant.id) & Q(sku__in=skus_list)).update(is_parser_active=True)


def show_successful_scrape_message(
    request: HttpRequest,
    items_data: list[dict],
    max_items_on_screen: int = config.MAX_ITEMS_ON_SCREEN,
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
        except (decimal.DivisionByZero, decimal.InvalidOperation):
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


def task_name(user: User) -> str:
    return f"task_tenant_{user.tenant.id}"


def periodic_task_exists(request: WSGIRequest) -> bool:
    """Checks for the existence of a periodic task with the given name."""

    try:
        PeriodicTask.objects.get(
            name=task_name(request),
        )
        return True
    except PeriodicTask.DoesNotExist:
        return False


def get_interval_russian_translation(periodic_task: PeriodicTask) -> str:
    """
    Translates the interval of a periodic task into Russian.

    It takes into account the grammatical rules of the Russian language for numbers and units of time.
    The function supports translation for seconds, minutes, hours, and days.

    Args:
        periodic_task (PeriodicTask): The periodic task object which contains the interval to be translated.

    Returns:
        str: A string in Russian that represents the interval of the periodic task.
             The string is in the format: "{every} {time_unit_number} {time_unit_name}" (e.g. "каждые 25 минут")
    """
    time_unit_number: int = periodic_task.interval.every
    time_unit_name: str = periodic_task.interval.period

    translations = {
        "seconds": ["секунду", "секунды", "секунд"],
        "minutes": ["минуту", "минуты", "минут"],
        "hours": ["час", "часа", "часов"],
        "days": ["день", "дня", "дней"],
    }

    every = "каждые"

    # 1, 21, 31, etc
    if time_unit_number % 10 == 1 and time_unit_number % 100 != 11:
        every = "каждую" if time_unit_name in ["seconds", "minutes"] else "каждый"
        time_unit_name = translations[time_unit_name][0]

    # 2-4, 22-24, 32-34, etc, excluding numbers ending in 12-14 (e.g. 12-14, 112-114, etc)
    elif 2 <= time_unit_number % 10 <= 4 and (time_unit_number % 100 < 12 or time_unit_number % 100 > 14):
        time_unit_name = translations[time_unit_name][1]

    else:
        time_unit_name = translations[time_unit_name][2]

    if time_unit_number == 1:
        return f"{every} {time_unit_name}"
    else:
        return f"{every} {time_unit_number} {time_unit_name}"


def check_plan_schedule_limitations(tenant: Tenant, period: str, interval: int) -> None:
    """
    Checks if the user has violated the plan limitations.

    Args:
        tenant (Tenant): The tenant object.
        period (str): The time unit (e.g., "hours", "days")
        interval (int): The interval value (e.g., 7, 24, 48)

    Raises:
        PlanScheduleLimitationException: If the user has violated the plan limitations.
    """
    # Currently, we only have schedule limitations for the FREE plan
    if tenant.payment_plan.name == PaymentPlan.PlanName.FREE.value:
        if period == "hours" and interval < 24:
            raise PlanScheduleLimitationException(
                tenant,
                plan=tenant.payment_plan.name,
                period=period,
                interval=interval,
                message="Ограничения бесплатного тарифа. Установите интервал не менее 24 часов",
            )


def get_user_quota(user: User) -> TenantQuota | None:
    """Get the user quota for a given user.

    Args:
        user (User): The user for which to get the quota.

    Returns:
        TenantQuota: The user quota for the given user.

    You can access the user quota fields like this:
        user_quota.user_lifetime_hours

        user_quota.max_allowed_skus

        user_quota.manual_updates

        user_quota.scheduled_updates
    """
    try:
        user_quota = user.tenant.quota
    except TenantQuota.DoesNotExist:
        user_quota = None

    return user_quota


def set_tenant_quota(
    tenant: Tenant,
    name: str = "DEMO_QUOTA",
    total_hours_allowed: int = config.DEMO_USER_HOURS_ALLOWED,
    skus_limit: int = config.DEMO_USER_MAX_ALLOWED_SKUS,
    parse_units_limit: int = config.DEMO_USER_ALLOWED_PARSE_UNITS,
) -> None:
    """Set the user quota for a given user."""
    tenant.quota, _ = TenantQuota.objects.get_or_create(
        name=name,
        total_hours_allowed=total_hours_allowed,
        skus_limit=skus_limit,
        parse_units_limit=parse_units_limit,
    )
    # assign the quota to the tenant
    tenant.save(update_fields=["quota"])


def create_demo_user() -> tuple[User, str]:
    """
    Create a demo user with a random name and password.
    """
    name_uuid = str(uuid4())
    password_uuid = str(uuid4())

    try:
        demo_user = User.objects.create(
            username=f"demo-user-{name_uuid}",
            email=f"demo-user-{name_uuid}@demo.com",
            is_demo_user=True,
            is_demo_active=True,
        )
        demo_user.set_password(password_uuid)
        demo_user.save()
    except IntegrityError as e:
        logger.error("Integrity error during demo user creation: %s", e)
        raise
    except ValidationError as e:
        logger.error("Validation error during demo user creation: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error during demo user creation: %s", e)
        raise

    logger.info("Demo user created with email: %s | password: %s", demo_user.email, password_uuid)
    return demo_user, password_uuid


def create_demo_items(demo_user: User) -> list[Item]:
    """Create demo items for the given user."""
    items = [
        {
            "tenant": demo_user.tenant,
            "name": "Таймер кухонный электронный для яиц на магните",
            "sku": "101231520",
            "price": 500,
        },
        {
            "tenant": demo_user.tenant,
            "name": "Гидрофильное гель-масло для умывания и очищения лица",
            "sku": "31299196",
            "price": 500,
        },
    ]

    created_items = []
    try:
        for item in items:
            created_item = Item.objects.create(**item)
            created_items.append(created_item)
    except IntegrityError as e:
        logger.error("Integrity error during demo items creation: %s", e)
        raise
    except ValidationError as e:
        logger.error("Validation error during demo items creation: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error during demo items creation: %s", e)
        raise

    return created_items


def no_active_demo_user(user: User) -> bool:
    """Make sure no active demo user exists for the user.
    Prevents the user from going directly to demo/ url and creating another demo session
    while the first one is still active.
    """
    return not (user.is_authenticated and hasattr(user, "is_demo_user") and user.is_demo_user)


def update_tenant_quota_for_max_allowed_sku(request: HttpRequest, skus: str) -> None:
    """
    Checks if the user has enough quota to scrape items and then updates the remaining user quota.

    Args:
        request: The HttpRequest object containing user and form data.
        skus (str): The string of SKUs to check.
    """
    user_quota = get_user_quota(request.user)
    skus_count = len(re.split(r"\s+|\n|,(?:\s*)", skus))  # count number of skus
    if skus_count <= user_quota.skus_limit:
        user_quota.skus_limit -= skus_count
        user_quota.save()
    else:
        raise QuotaExceededException(
            message=(
                "Превышен лимит количества товаров для данного тарифа. %s / %s",
                skus_count,
                user_quota.skus_limit,
            ),
            quota_type="max_allowed_skus",
        )


def update_user_quota_for_allowed_parse_units(user: User, skus: str) -> None:
    user_quota = get_user_quota(user)
    skus_count = len(re.split(r"\s+|\n|,(?:\s*)", skus))
    if user_quota.parse_units_limit >= skus_count:
        user_quota.parse_units_limit -= skus_count
        user_quota.save()
    else:
        raise QuotaExceededException(
            message="Превышен лимит единиц проверки для данного тарифа.",
            quota_type="allowed_parse_units",
        )


class MerchantSignatureGenerator:
    """
    API reference: https://modulbank.ru/support/formation_payment_request

    Generate a signature for merchant payments based on the secret key.
    "merchant" is the merchant ID (get it from the merchant dashboard; not a required field).
    "salt" is a random string that is used to prevent replay attacks (not a required field).
    secret_key = settings.PAYMENT_TEST_SECRET_KEY

    Example of use:
    secret_key = settings.PAYMENT_TEST_SECRET_KEY

    items = {
        "testing": "1",
        "salt": "xafAFruTVrpwHKjvZoHvSVkUeMqZoefp",
        "order_id": "43683694",
        "amount": "555",
        "merchant": "f29e4787-0c3b-4630-9340-5dcfcdc9f85d",
        "description": "Заказ №43683693",
        "client_phone": "+7 (700) 675-87-89",
        "client_email": "test@test.ru",
        "client_name": "Тестов Тест Тестович",
        "success_url": "https://pay.modulbank.ru/success",
        "unix_timestamp": "1723447580",
    }

    generator = MerchantSignatureGenerator(secret_key)
    print(generator.get_signature(items))

    """

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def get_raw_signature(self, params: dict) -> str:
        """Generate a raw signature string from the sorted parameters."""
        chunks = []

        for key in sorted(params.keys()):
            if key == "signature":
                continue

            value = params[key]

            if isinstance(value, str):
                value = value.encode("utf8")
            else:
                value = str(value).encode("utf-8")

            if not value:
                continue

            value_encoded = base64.b64encode(value)
            chunks.append(f"{key}={value_encoded.decode()}")

        raw_signature = "&".join(chunks)
        return raw_signature

    def double_sha1(self, data: str) -> str:
        """Apply double SHA1 hashing based on the secret key."""
        sha1_hex = lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest()  # noqa
        digest = sha1_hex(self.secret_key + sha1_hex(self.secret_key + data))
        return digest

    def get_signature(self, params: dict) -> str:
        """Calculate the signature based on the parameters."""
        raw_signature = self.get_raw_signature(params)
        return self.double_sha1(raw_signature)


def create_unique_order_id(tenant_id: int, max_attempts: int = 10) -> str:
    """Create a unique order ID for the given tenant."""
    for _ in range(max_attempts):
        order_id = f"{tenant_id}{str(uuid.uuid4().int)[:5]}"
        if not Order.objects.filter(order_id=order_id).exists():
            logger.debug("Created new order ID: %s", order_id)
            return order_id
    logger.error("Не удалось создать заказ для оплаты. Попробуйте еще раз. Tenant ID: %s", tenant_id)
    raise ValueError("Не удалось создать заказ для оплаты. Попробуйте еще раз.")
