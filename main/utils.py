# import this here if you encounter the following error:
# django.core.exceptions.ImproperlyConfigured: Requested setting USE_DEPRECATED_PYTZ, but settings are not configured.
# You must either define the environment variable DJANGO_SETTINGS_MODULE or call settings.configure() before accessing
# settings.
# os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mp_monitor.settings")
# django.setup()


# def scrape_live_price(sku):
#     """Scrapes the live price of a product from Wildberries.
#
#     Args:
#         sku (str): The SKU of the product.
#
#     Returns:
#         int: The live price of the product.
#     """
#     logger.info("Starting to scrape live price")
#     chrome_options = Options()
#     chrome_options.add_argument("--headless")
#     # chrome_options.add_argument("--no-sandbox")
#     # chrome_options.add_argument("--disable-dev-shm-usage")
#     driver = webdriver.Chrome(options=chrome_options)
#     # driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
#
#     regular_link = f"https://www.wildberries.ru/catalog/{sku}/detail.aspx"
#     driver.get(regular_link)
#     # Wait for the presence of the price element
#     try:
#         price_element = WebDriverWait(driver, 10).until(
#             EC.presence_of_element_located(
#                 (
#                     By.XPATH,
#                     (
#                         "//div[@class='product-page__price-block product-page__price-block--aside']//ins["
#                         "@class='price-block__final-price']"
#                     ),
#                 )
#             )
#         )
#     except TimeoutException:
#         price_element = None
#
#     if price_element is not None:
#         parsed_price = price_element.get_attribute("textContent").replace("₽", "").replace("\xa0", "").strip()
#         parsed_price = int(parsed_price)
#         print(f"My final price ee: {parsed_price} ({type(parsed_price)})")
#     else:
#         parsed_price = 0
#         print("Parsed price is ZERO")
#
#     return parsed_price


# def extract_price_before_spp(item: dict) -> float | None:
#     # original_price = item["priceU"]
#     sale = 0
#     try:
#         original_price = item["sizes"][0]["price"]["basic"]
#         discount = original_price * (int(sale) / 100)
#         price_before_spp = original_price - discount
#         logger.info("Price before SPP = %s", price_before_spp)
#         return float(price_before_spp) / 100
#     except (KeyError, TypeError):
#         logger.error("Could not extract price before SPP from item: %s", item)
#         return None


# def check_item_stock(item: dict) -> bool:
#     sku = item.get("id")
#     # Item availability is hidden in item.sizes[0].stocks
#     is_in_stock = any(item["stocks"] for item in item.get("sizes", []))
#
#     if is_in_stock:
#         logger.info("At least one item for sku (%s) is in stock.", sku)
#     else:
#         logger.info("No items for sku (%s) are in stock.", sku)
#
#     return is_in_stock


# def is_sku_format_valid(sku: str) -> bool:
#     """Check if the SKU has a valid format.
#
#     Args:
#         sku (str): The SKU to check.
#
#     Returns:
#         bool: True if the SKU is valid, False otherwise.
#     """
#     # only numbers, between 5-12 characters long
#     if re.match(r"^[0-9]{4,12}$", sku):
#         return True
#     else:
#         return False


# def is_item_exists(item_info: list) -> bool:
#     """Check if item exists on Wildberries.
#
#     Non-existing items return an empty list.
#     """
#     if item_info:
#         return True
#     return False


# WB's API constantly changes. Right now:
#   no "extended" field in API
#   priceU = the price before every discount (scratched out)
#   sale = seller discount
#   salePriceU = the final price (aka, price with spp, no need for Selenium here)
# def scrape_item(sku: str, use_selenium: bool = False) -> dict:
#     """
#     Scrape item from WB's API.
#
#     Args:
#         sku (str): The SKU of the product.
#         use_selenium (bool): Whether to use Selenium to scrape the live price (slower).
#
#     Returns:
#         dict: A dictionary containing the data for the scraped item.
#
#     Raises:
#         InvalidSKUException: If the provided SKU is invalid
#     """
#
#     if not is_sku_format_valid(sku):
#         logger.error("Invalid format for SKU: %s", sku)
#         raise InvalidSKUException(message="Invalid format for SKU.", sku=sku)
#
#     if use_selenium:
#         logger.info("Going to scrape live for sku: %s", sku)
#         price_after_spp = scrape_live_price(sku)
#         logger.info("Live price: %s", price_after_spp)
#
#     # Looks like this: https://card.wb.ru/cards/detail?appType=1&curr=rub&dest=-455203&nm={sku}
#     url = httpx.URL(
#         "https://card.wb.ru/cards/v2/detail",
#         params={"appType": 1, "curr": "rub", "dest": 123589330, "nm": sku},
#     )
#     # pylint: disable=line-too-long
#
#     headers = {  # noqa
#         "User-Agent": (
#             "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
#         ),
#         "Accept": "*/*",
#         "Accept-Encoding": "gzip, deflate, br",
#         "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
#         "Origin": "https://www.wildberries.ru",
#     }
#     retry_count = 0
#     data = {}
#
#     logger.info("Starting while loop...")
#     # in case of a server error, retry the request up to MAX_RETRIES times
#     # TODO: check if we can use a separate function connect() with a @retry decorator like so
#     # https://github.com/federicoazzu/five_decorators/tree/main/decorators
#     while retry_count < config.MAX_RETRIES:
#         try:
#             response = httpx.get(url, timeout=60)
#             response.raise_for_status()
#             data = response.json()
#             if data:
#                 logger.info("Breaking the loop...")
#                 break
#         except httpx.HTTPError as e:
#             logger.error(
#                 "HTTP error occurred: %s. Failed to scrape url: %s. Attempt #%s",
#                 e,
#                 url,
#                 retry_count + 1,
#             )
#             retry_count += 1
#             # using exponential backoff for HTTP requests to handle rate limits and network issues more gracefully
#             sleep_amount_sec = min(60, 2**retry_count)
#             logger.info("Sleeping for %s seconds", sleep_amount_sec)
#             time.sleep(sleep_amount_sec)
#     logger.info("Exited while loop...")
#
#     item_info: list = data.get("data", {}).get("products")
#     if not is_item_exists(item_info):
#         raise InvalidSKUException(message="Request returned no item for SKU.", sku=sku)
#
#     item = data.get("data", {}).get("products")[0]
#
#     # makes sure that the correct id (i.e. = sku) is being pulled from api
#     if item.get("id") != sku:
#         for product in data.get("data", {}).get("products"):
#             if product.get("id") == sku:
#                 item = product
#                 logger.info("Found item with SKU: %s", sku)
#                 break
#
#     name = item.get("name")
#     sku = item.get("id")
#     # price with only seller discount, no longer used in WB API
#     price_before_spp = extract_price_before_spp(item) or 0
#     logger.info("Checking if item is in stock")
#     is_in_stock = check_item_stock(item)
#     if is_in_stock:
#         logger.info("Item with SKU %s is in stock. Checking price...", sku)
#         price_after_spp = item["sizes"][0]["price"]["total"] / 100
#     else:
#         logger.info("Item is out of stock")
#         price_after_spp = None
#     image = item.get("image")
#     category = item.get("category")
#     brand = item.get("brand")
#     seller_name = item.get("brand")
#     rating = float(item.get("rating")) if item.get("rating") is not None else None
#     num_reviews = int(item.get("feedbacks")) if item.get("feedbacks") is not None else None
#
#     logger.info("seller_price: %s", price_before_spp)
#     if price_before_spp is None:
#         logger.error("Could not find seller's price for sku %s", sku)
#
#     price_before_any_discount = (
#         item.get("priceU") / 100 if (item.get("priceU") and isinstance(item.get("priceU"), int)) else None
#     )
#
#     try:
#         seller_discount = item["extended"]["basicSale"]
#     except KeyError:
#         # seller_discount = item["sale"]
#         seller_discount = 0
#
#     try:
#         spp = round(((price_before_spp - price_after_spp) / price_before_spp) * 100)
#     except TypeError as e:
#         logger.error(
#             "Could not calculate SPP for sku %s using price_before_spp (%s) and price_after_spp (%s). Error: %s",
#             sku,
#             price_before_spp,
#             price_after_spp,
#             e,
#         )
#         spp = 0
#     except ZeroDivisionError:
#         logger.error(
#             "Could not calculate SPP. Division by zero occurred for sku %s using price_before_spp (%s) and"
#             " price_after_spp (%s)",
#             sku,
#             price_before_spp,
#             price_after_spp,
#         )
#         spp = None
#
#     # breakdown of all types of prices and SPP (SPP currently is incorrect)
#     logger.info("Price before any discount: %s", price_before_any_discount)
#     logger.info("Seller's discount: %s", seller_discount)
#     logger.info("Seller's price: %s", price_before_spp)
#     logger.info("SPP: %s%%", spp)  # e.g. SPP: 5%
#     logger.info("Live price on WB: %s", price_after_spp)
#
#     return {
#         "name": name,
#         "sku": sku,
#         "seller_price": price_before_spp,
#         "price": price_after_spp,
#         "spp": spp,
#         "image": image,
#         "category": category,
#         "brand": brand,
#         "seller_name": seller_name,
#         "rating": rating,
#         "num_reviews": num_reviews,
#         "is_in_stock": is_in_stock,
#     }


# def scrape_items_from_skus(skus: str, is_parser_active: bool = False) -> tuple[list[dict[str, Any]], list[str]]:
#     """Scrapes item data from a string of SKUs.
#
#     Args:
#         skus: A string containing SKUs, separated by spaces, newlines, or commas.
#
#     Returns a tuple consisting of:
#         - A list of dictionaries, where each dictionary contains the data for a single item.
#         - A list with invalid SKUs
#     """
#     logger.info("Going to scrape items: %s", skus)
#     items_data = []
#     invalid_skus = []
#     # TODO: introduce sleep and improve UX: https://github.com/igorsimb/mp-monitor/issues/164
#     for sku in re.split(r"\s+|\n|,(?:\s*)", skus):
#         logger.info("Scraping item: %s", sku)
#         try:
#             item_data = scrape_item(sku)
#             items_data.append(item_data)
#             if is_parser_active:
#                 item_data["is_parser_active"] = True
#         except InvalidSKUException as e:
#             invalid_skus.append(e.sku)
#     return items_data, invalid_skus


# def update_or_create_items(request: HttpRequest, items_data: List[Dict[str, Any]]) -> None:
#     """
#     Update existing items or create new ones for the user's tenant.
#
#     Args:
#         request (HttpRequest): The HTTP request object with user information.
#         items_data (List[Dict[str, Any]]): List of item data dictionaries.
#
#     Returns:
#         None
#     """
#     logger.info("Update request=%s", request)
#     for item_data in items_data:
#         item, created = Item.objects.update_or_create(  # pylint: disable=unused-variable
#             tenant=request.user.tenant,
#             sku=item_data["sku"],
#             defaults=item_data,
#         )


# def update_or_create_items_interval(tenant_id, items_data):
#     logger.info("Update tenant_id=%s", tenant_id)
#     tenant = Tenant.objects.get(id=tenant_id)
#     logger.info("Update tenant=%s", tenant)
#     for item_data in items_data:
#         item, created = Item.objects.update_or_create(  # pylint: disable=unused-variable
#             tenant=tenant,
#             sku=item_data["sku"],
#             defaults=item_data,
#         )


# def is_at_least_one_item_selected(request: HttpRequest, selected_item_ids: list[str] | str) -> bool:
#     """Checks if at least one item is selected.
#
#     If not, displays an error message and redirects to the item list page.
#     Args:
#         request: The HttpRequest object.
#         selected_item_ids: A list of stringified integers representing the IDs of the selected items.
#     """
#     if not selected_item_ids:
#         messages.error(request, "Выберите хотя бы 1 товар")
#         logger.warning("No items were selected. Task not created.")
#         return False
#
#     logger.info("Items with these ids where selected: %s", selected_item_ids)
#     return True


# def uncheck_all_boxes(request: HttpRequest) -> None:
#     """Unchecks all boxes in the item list page.
#
#     Since HTML checkboxes don't inherently signal when unchecked,
#      we uncheck everything so that later on an **updated** items list can be checked
#     """
#     logger.info("Unchecking all boxes in the item list page.")
#     Item.objects.filter(tenant=request.user.tenant.id).update(is_parser_active=False)  # type: ignore
#     logger.info("All boxes unchecked.")


# def activate_parsing_for_selected_items(request: WSGIRequest, skus_list: list[int]) -> None:
#     """Activates parsing for the specified items by setting their `is_parser_active` field to True.
#     Performs a single update operation to the database while making sure this operation is atomic and
#     no other operations run while this is in progress.
#     """
#     Item.objects.filter(Q(tenant_id=request.user.tenant.id) & Q(sku__in=skus_list)).update(is_parser_active=True)


# def show_successful_scrape_message(request: HttpRequest, items_data: List[Dict[str, Any]], max_items_on_screen: int) -> None:
#     """Show success message after scraping items."""
#     if len(items_data) == 1:
#         messages.success(
#             request,
#             mark_safe(
#                 f"Товар <b>{items_data[0]['name']}</b> успешно добавлен.<br>"
#                 f"Артикул: {items_data[0]['sku']}"
#             ),
#         )
#     else:
#         items_to_show = items_data[:max_items_on_screen]
#         remaining_items = len(items_data) - max_items_on_screen
#
#         message = "Следующие товары успешно добавлены:<br>"
#         for item in items_to_show:
#             message += f"• {item['name']} (арт. {item['sku']})<br>"
#
#         if remaining_items > 0:
#             message += f"... и еще {remaining_items} товаров"
#
#         messages.success(request, mark_safe(message))


# def show_invalid_skus_message(request: HttpRequest, invalid_skus: list) -> None:
#     """Show warning message for invalid SKUs."""
#     if len(invalid_skus) == 1:
#         messages.warning(
#             request,
#             f"Не удалось добавить следующий артикул: {', '.join(invalid_skus)}<br>"
#             "Возможен неверный формат артикула, или товара с таким артикулом не существует. "
#             "Пожалуйста, проверьте его корректность и при возникновении вопросов обратитесь в службу поддержки.",
#         )
#     else:
#         messages.warning(
#             request,
#             f"Не удалось добавить следующие артикулы: {', '.join(invalid_skus)}<br>"
#             "Возможен неверный формат артикулов, или товаров с такими артикулами не существует. "
#             "Пожалуйста, проверьте их корректность и при возникновении вопросов обратитесь в службу поддержки.",
#         )


# def calculate_percentage_change(prices: Page) -> None:
#     """Calculate percentage change between consecutive prices."""
#     for i in range(len(prices)):
#         try:
#             previous_price = prices[i + 1].value
#             current_price = prices[i].value
#             percent_change = ((current_price - previous_price) / previous_price) * 100
#             prices[i].percent_change = round(percent_change, 2)
#         except (IndexError, InvalidOperation, DivisionByZero):
#             prices[i].percent_change = 0
#         except TypeError:
#             logger.warning("Can't compare price to NoneType")


# def add_table_class(prices: Page) -> None:
#     """Add Bootstrap table classes based on price changes."""
#     for i in range(len(prices)):
#         try:
#             if prices[i].percent_change > 0:
#                 prices[i].table_class = "table-danger"
#             elif prices[i].percent_change < 0:
#                 prices[i].table_class = "table-success"
#             else:
#                 prices[i].table_class = ""
#         except (AttributeError, TypeError):
#             prices[i].table_class = ""


# def add_price_trend_indicator(prices: Page) -> None:
#     """Add trend indicators to a list of Price objects based on price comparison."""
#     for i in range(len(prices)):
#         try:
#             if prices[i].value < prices[i + 1].value:
#                 prices[i].trend = "↓"
#             elif prices[i].value > prices[i + 1].value:
#                 prices[i].trend = "↑"
#             else:
#                 prices[i].trend = ""
#         except IndexError:
#             prices[i].table_class = ""
#         except TypeError:
#             logger.warning("Can't compare price to NoneType")


# def check_plan_schedule_limitations(tenant: Tenant, period: str, interval: int) -> None:
#     """
#     Checks if the user has violated the plan limitations.
#
#     Args:
#         tenant (Tenant): The tenant object.
#         period (str): The time unit (e.g., "hours", "days")
#         interval (int): The interval value (e.g., 7, 24, 48)
#
#     Raises:
#         PlanScheduleLimitationException: If the user has violated the plan limitations.
#     """
#     # Currently, we only have schedule limitations for the FREE plan
#     if tenant.payment_plan.name == PaymentPlan.PlanName.FREE.value:
#         if period == "hours" and interval < 24:
#             raise PlanScheduleLimitationException(
#                 tenant,
#                 plan=tenant.payment_plan.name,
#                 period=period,
#                 interval=interval,
#                 message="Ограничения бесплатного тарифа. Установите интервал не менее 24 часов",
#             )


# def get_user_quota(user: User) -> TenantQuota | None:
#     """Get the user quota for a given user.
#
#     Args:
#         user (User): The user for which to get the quota.
#
#     Returns:
#         TenantQuota: The user quota for the given user.
#
#     You can access the user quota fields like this:
#         user_quota.user_lifetime_hours
#
#         user_quota.max_allowed_skus
#
#         user_quota.manual_updates
#
#         user_quota.scheduled_updates
#     """
#     try:
#         user_quota = user.tenant.quota
#     except TenantQuota.DoesNotExist:
#         user_quota = None
#
#     return user_quota


# def set_tenant_quota(
#     tenant: Tenant,
#     name: str = "DEMO_QUOTA",
#     total_hours_allowed: int = config.DEMO_USER_HOURS_ALLOWED,
#     skus_limit: int = config.DEMO_USER_MAX_ALLOWED_SKUS,
#     parse_units_limit: int = config.DEMO_USER_ALLOWED_PARSE_UNITS,
# ) -> None:
#     """Set the user quota for a given user."""
#     tenant.quota, _ = TenantQuota.objects.get_or_create(
#         name=name,
#         total_hours_allowed=total_hours_allowed,
#         skus_limit=skus_limit,
#         parse_units_limit=parse_units_limit,
#     )
#     # assign the quota to the tenant
#     tenant.save(update_fields=["quota"])


# def update_tenant_quota_for_max_allowed_sku(request: HttpRequest, skus: str) -> None:
#     """Update tenant quota for maximum allowed SKUs.
#
#     Args:
#         request: The HTTP request object.
#         skus: Space-separated string of SKUs.
#
#     Raises:
#         QuotaExceededException: If the tenant has exceeded their SKU quota.
#     """
#     tenant_quota = request.user.tenant.quota
#     if tenant_quota is None:
#         return
#
#     skus_list = skus.split()
#     current_items_count = request.user.tenant.items.count()
#     new_items_count = len(skus_list)
#
#     if current_items_count + new_items_count > tenant_quota.skus_limit:
#         raise QuotaExceededException(
#             f"Превышен лимит в {tenant_quota.skus_limit} товаров для демо-аккаунта. "
#             f"Текущее количество товаров: {current_items_count}. "
#             f"Попытка добавить еще {new_items_count} товаров."
#         )


# def update_user_quota_for_allowed_parse_units(user: User, skus: str) -> None:
#     """Update user quota for allowed parse units.
#
#     Args:
#         user: The user object.
#         skus: Space-separated string of SKUs.
#
#     Raises:
#         QuotaExceededException: If the user has exceeded their parse units quota.
#     """
#     tenant_quota = user.tenant.quota
#     if tenant_quota is None:
#         return
#
#     skus_list = skus.split()
#     if len(skus_list) > tenant_quota.parse_units_limit:
#         raise QuotaExceededException(
#             f"Превышен лимит в {tenant_quota.parse_units_limit} товаров за один запрос для демо-аккаунта. "
#             f"Попытка спарсить {len(skus_list)} товаров."
#         )


# def create_unique_order_id() -> str:
#     """Create a unique order ID.
#
#     Returns:
#         str: A unique order ID.
#
#     Raises:
#         ValidationError: If unable to generate a unique ID after multiple attempts.
#     """
#     max_attempts = 10
#     attempt = 0
#
#     while attempt < max_attempts:
#         order_id = str(uuid4())
#         if not Order.objects.filter(order_id=order_id).exists():
#             return order_id
#         attempt += 1
#
#     raise ValidationError("Unable to generate a unique order ID")


# def create_demo_user() -> tuple[User, str]:
#     """
#     Create a demo user with a random name and password.
#     """
#     name_uuid = str(uuid4())
#     password_uuid = str(uuid4())
#
#     try:
#         demo_user = User.objects.create(
#             username=f"demo-user-{name_uuid}",
#             email=f"demo-user-{name_uuid}@demo.com",
#             is_demo_user=True,
#             is_demo_active=True,
#         )
#         demo_user.set_password(password_uuid)
#         demo_user.save()
#     except IntegrityError as e:
#         logger.error("Integrity error during demo user creation: %s", e)
#         raise
#     except ValidationError as e:
#         logger.error("Validation error during demo user creation: %s", e)
#         raise
#     except Exception as e:
#         logger.error("Unexpected error during demo user creation: %s", e)
#         raise
#
#     logger.info("Demo user created with email: %s | password: %s", demo_user.email, password_uuid)
#     return demo_user, password_uuid
#
#
# def create_demo_items(demo_user: User) -> list[Item]:
#     """Create demo items for the given user."""
#     items = [
#         {
#             "tenant": demo_user.tenant,
#             "name": "Таймер кухонный электронный для яиц на магните",
#             "sku": "101231520",
#             "price": 500,
#         },
#         {
#             "tenant": demo_user.tenant,
#             "name": "Гидрофильное гель-масло для умывания и очищения лица",
#             "sku": "31299196",
#             "price": 500,
#         },
#     ]
#
#     created_items = []
#     try:
#         for item in items:
#             created_item = Item.objects.create(**item)
#             created_items.append(created_item)
#     except IntegrityError as e:
#         logger.error("Integrity error during demo items creation: %s", e)
#         raise
#     except ValidationError as e:
#         logger.error("Validation error during demo items creation: %s", e)
#         raise
#     except Exception as e:
#         logger.error("Unexpected error during demo items creation: %s", e)
#         raise
#
#     return created_items
#
#
# def no_active_demo_user(user: User) -> bool:
#     """Make sure no active demo user exists for the user.
#     Prevents the user from going directly to demo/ url and creating another demo session
#     while the first one is still active.
#     """
#     return not (user.is_authenticated and hasattr(user, "is_demo_user") and user.is_demo_user)
