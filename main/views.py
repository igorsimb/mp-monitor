import json
import locale
import logging
from datetime import timedelta

import requests
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models.query import QuerySet
from django.http import HttpResponseRedirect, HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import ListView, DetailView
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django_ratelimit.core import is_ratelimited
from guardian.mixins import PermissionListMixin, PermissionRequiredMixin

import config
import main.plotly_charts as plotly_charts
from accounts.forms import SwitchPlanForm
from accounts.models import PaymentPlan
from mp_monitor import settings
from .exceptions import QuotaExceededException, PlanScheduleLimitationException
from .forms import ScrapeForm, ScrapeIntervalForm, UpdateItemsForm, PriceHistoryDateForm, PaymentForm
from .models import Item, Price, Order
from .payment_utils import (
    validate_callback_data,
    update_payment_records,
    TinkoffTokenGenerator,
    get_price_per_parse,
)
from .utils import (
    uncheck_all_boxes,
    show_successful_scrape_message,
    is_at_least_one_item_selected,
    scrape_items_from_skus,
    update_or_create_items,
    calculate_percentage_change,
    add_table_class,
    add_price_trend_indicator,
    periodic_task_exists,
    show_invalid_skus_message,
    activate_parsing_for_selected_items,
    task_name,
    get_interval_russian_translation,
    get_user_quota,
    update_tenant_quota_for_max_allowed_sku,
    update_user_quota_for_allowed_parse_units,
    # MerchantSignatureGenerator,
    check_plan_schedule_limitations,
    create_unique_order_id,
)

user = get_user_model()
logger = logging.getLogger(__name__)
locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")  # Set the locale to Russian


def index(request):
    """The entry point for the website."""
    if request.user.is_authenticated:
        return redirect("item_list")
    return render(request, "main/index.html")


class ItemListView(PermissionListMixin, LoginRequiredMixin, ListView):
    # TODO: add min/max pills if min or max
    model = Item
    context_object_name = "items"
    permission_required = ["view_item"]
    template_name = "main/item_list.html"

    ordering = ["-updated_at"]
    paginate_by = 25

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = ScrapeForm()
        update_items_form = UpdateItemsForm()
        scrape_interval_form = ScrapeIntervalForm(user=self.request.user)
        demo_users = user.objects.filter(is_demo_user=True)
        inactive_demo_users = user.objects.filter(is_demo_user=True, is_active=False)
        active_demo_users = user.objects.filter(is_demo_user=True, is_active=True)
        expired_active_demo_users = [user for user in active_demo_users if user.is_demo_expired]
        non_expired_active_demo_users = [user for user in active_demo_users if not user.is_demo_expired]
        tenant_quota = get_user_quota(self.request.user)

        time_since_user_created = timezone.now() - self.request.user.created_at
        if get_user_quota(self.request.user) is not None:
            remaining_time = timedelta(hours=tenant_quota.total_hours_allowed) - time_since_user_created
            remaining_hours = remaining_time.seconds // 3600
            remaining_minutes = (remaining_time.seconds % 3600) // 60
            context["demo_remaining_time"] = f"{remaining_hours} ч. {remaining_minutes} мин."

        try:
            periodic_task = PeriodicTask.objects.get(name=task_name(self.request.user))
        except PeriodicTask.DoesNotExist:
            periodic_task = None

        sku = None
        context["sku"] = sku
        context["form"] = form
        context["demo_users"] = demo_users
        context["inactive_demo_users"] = inactive_demo_users
        context["non_expired_active_demo_users"] = non_expired_active_demo_users
        context["expired_active_demo_users"] = expired_active_demo_users
        context["update_items_form"] = update_items_form
        context["scrape_interval_form"] = scrape_interval_form
        context["tenant_quota"] = tenant_quota
        context["demo_user_lifetime_hours"] = int(config.DEMO_USER_HOURS_ALLOWED)
        context["demo_max_allowed_skus"] = int(config.DEMO_USER_MAX_ALLOWED_SKUS)
        context["demo_allowed_parse_units"] = int(config.DEMO_USER_ALLOWED_PARSE_UNITS)
        if periodic_task:
            schedule_interval = periodic_task.schedule.run_every
            context["scrape_interval_task"] = get_interval_russian_translation(periodic_task)
            context["next_interval_run_at"] = periodic_task.last_run_at + schedule_interval
        return context

    def get_queryset(self) -> QuerySet[Item]:
        queryset = super().get_queryset()
        return queryset.filter(tenant=self.request.user.tenant)

    def get(self, request, *args, **kwargs):
        logger.info("Going to Item List page")
        return super().get(request, *args, **kwargs)


class ItemDetailView(PermissionRequiredMixin, DetailView):
    model = Item
    permission_required = ["view_item"]
    template_name = "main/item_detail.html"
    context_object_name = "item"
    slug_field = "sku"

    def get_context_data(self, **kwargs) -> dict:
        items_per_page = 15
        context = super().get_context_data(**kwargs)

        prices = Price.objects.filter(item=self.object)
        start_date = self.request.GET.get("start_date")
        end_date = self.request.GET.get("end_date")

        paginator = Paginator(prices, items_per_page)
        page_number = self.request.GET.get("page")
        prices_paginated = paginator.get_page(page_number)

        calculate_percentage_change(prices_paginated)
        add_table_class(prices_paginated)
        add_price_trend_indicator(prices_paginated)

        item_updated_at = self.object.updated_at
        price_created_at = self.object.prices.latest("created_at")

        tenant_quota = get_user_quota(self.request.user)
        time_since_user_created = timezone.now() - self.request.user.created_at
        if get_user_quota(self.request.user) is not None:
            remaining_time = timedelta(hours=tenant_quota.total_hours_allowed) - time_since_user_created
            remaining_hours = remaining_time.seconds // 3600
            remaining_minutes = (remaining_time.seconds % 3600) // 60
            context["demo_remaining_time"] = f"{remaining_hours} ч. {remaining_minutes} мин."

        context["price_history_date_form"] = PriceHistoryDateForm()
        context["start_date"] = start_date
        context["end_date"] = end_date
        context["prices_paginated"] = prices_paginated
        context["item_updated_at"] = item_updated_at
        context["price_created_at"] = price_created_at
        context["tenant_quota"] = tenant_quota
        context["demo_user_lifetime_hours"] = int(config.DEMO_USER_HOURS_ALLOWED)
        context["demo_max_allowed_skus"] = int(config.DEMO_USER_MAX_ALLOWED_SKUS)
        context["demo_allowed_parse_units"] = int(config.DEMO_USER_ALLOWED_PARSE_UNITS)
        return context

    def get_queryset(self) -> QuerySet[Item]:
        queryset = super().get_queryset()
        return queryset.filter(tenant=self.request.user.tenant)

    def get(self, request, *args, **kwargs):
        logger.info(
            "Going to Details Page for item SKU '%s' (%s)",
            self.get_object().sku,
            self.get_object().name,
        )
        return super().get(request, *args, **kwargs)


def load_chart(request, sku):
    """
    Load and return a Plotly chart for a specific item's price history.

    This view function retrieves the price history for a given item (identified by its SKU),
    generates a Plotly chart, and returns it as an HTTP response. The chart can be filtered
    by start and end dates if provided in the request.

    Args:
        request (HttpRequest): The HTTP request object.
        sku (str): The Stock Keeping Unit (SKU) of the item.

    Notes:
        - The function expects the user to be authenticated and have a associated tenant.
        - Start and end dates for filtering can be provided as GET parameters.
        - The chart is generated using the create_price_history_chart function from plotly_charts module.
        - in template use HTMX to render it on load, e.g.: hx-get="{% url 'load_chart' item.sku %}" hx-trigger="load"
    """
    item = get_object_or_404(Item, sku=sku, tenant=request.user.tenant)
    prices = Price.objects.filter(item=item)
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    price_history_chart = plotly_charts.create_price_history_chart(prices, start_date, end_date)
    return HttpResponse(price_history_chart)


# TODO: consider renaming this function to add_new_items or something similar
def scrape_items(request: WSGIRequest, skus: str) -> HttpResponse | HttpResponseRedirect:
    """Scrapes items from the given SKUs taken from the form data"""
    if is_ratelimited(request, group="scrape_items", key="user_or_ip", method="POST", rate="10/m", increment=True):
        messages.error(request, "Вы сделали слишком много запросов на парсинг товаров. Попробуйте позже.")
        logger.error("Request limit exceeded for scrape_items, user: %s", request.user)
        return redirect("item_list")

    if request.method == "POST":
        form = ScrapeForm(request.POST)
        if form.is_valid():
            skus = form.cleaned_data["skus"]

            if get_user_quota(request.user) is not None:
                try:
                    logger.info("Trying to update demo user quota for max allowed skus...")
                    update_tenant_quota_for_max_allowed_sku(request, skus)
                    update_user_quota_for_allowed_parse_units(request.user, skus)
                except QuotaExceededException as e:
                    logger.warning(e.message)
                    messages.error(request, e.message)
                    return redirect("item_list")

            logger.info("Scraping items with SKUs: %s", skus)
            items_data, invalid_skus = scrape_items_from_skus(skus)
            update_or_create_items(request, items_data)
            show_successful_scrape_message(request, items_data, max_items_on_screen=10)

            if invalid_skus:  # check if there are invalid SKUs
                show_invalid_skus_message(request, invalid_skus)  # pragma: no cover

            return redirect("item_list")
    else:
        form = ScrapeForm()

    context = {"form": form}
    return render(request, "main/item_list.html", context)


def update_items(request: WSGIRequest) -> HttpResponse | HttpResponseRedirect:
    """Scrapes selected items"""

    if is_ratelimited(request, group="update_items", key="user_or_ip", method="POST", rate="10/m", increment=True):
        messages.error(request, "Слишком много запросов на обновление товаров. Попробуйте позже.")
        logger.error("Request limit exceeded for update_items, user: %s", request.user)
        return redirect("item_list")

    if request.method == "POST":
        form = UpdateItemsForm(request.POST)
        if form.is_valid():
            skus = request.POST.getlist("selected_items")

            # Convert the list of stringified numbers to a string of integers for scrape_items_from_skus:
            skus = " ".join(skus)
            logger.info("Beginning to update items info...")
            if not is_at_least_one_item_selected(request, skus):
                return redirect("item_list")

            #  needs to be placed after is_at_least_one_item_selected check to avoid updating quota despite the error
            if get_user_quota(request.user) is not None:
                try:
                    update_user_quota_for_allowed_parse_units(request.user, skus)
                except QuotaExceededException as e:
                    messages.error(request, e.message)
                    return redirect("item_list")

            # scrape_items_from_skus returns a tuple, but only the first part is needed for update_or_create_items
            items_data, _ = scrape_items_from_skus(skus)
            update_or_create_items(request, items_data)
            show_successful_scrape_message(request, items_data, max_items_on_screen=10)

            return redirect("item_list")
        else:
            logger.error("Form is invalid. %s", form.errors)
            messages.error(
                request,
                "Что-то пошло не так. Попробуйте еще раз или обратитесь к администратору.",
            )
            return redirect("item_list")
    else:
        form = UpdateItemsForm()
    return render(request, "main/item_list.html", {"update_items_form": form})


def create_scrape_interval_task(
    request: WSGIRequest,
) -> HttpResponse | HttpResponseRedirect:
    """Takes interval from the form data (in seconds) and triggers main.tasks.scrape_interval_task

    The task itself prints all items belonging to this tenant every {{ interval }} seconds.
    """

    if request.method == "POST":
        scrape_interval_form = ScrapeIntervalForm(request.POST or None, user=request.user)

        if scrape_interval_form.is_valid():
            logger.info("Starting the task")
            skus = request.POST.getlist("selected_items")

            # Convert the list of stringified numbers to a string of integers for scrape_items_from_skus:
            skus = " ".join(skus)

            # if not is_at_least_one_item_selected(request, selected_item_ids):
            if not is_at_least_one_item_selected(request, skus):
                return redirect("item_list")

            uncheck_all_boxes(request)

            # Convert the list of stringified numbers to a list of integers to avoid the following error:
            # json.decoder.JSONDecodeError: Expecting value: line 1 column 6 (char 5)
            # selected_item_ids = [int(item) for item in selected_item_ids]
            skus_list = skus.split(" ")
            skus_list = [int(sku) for sku in skus_list]

            interval = scrape_interval_form.cleaned_data["interval_value"]
            period = scrape_interval_form.cleaned_data["period"]

            # Limit the interval to 24 hours for free users
            # if request.user.tenant.payment_plan.name == PaymentPlan.PlanName.FREE.value:
            #     if period == "hours" and interval < 24:
            #         messages.error(request, "Ограничения бесплатного тарифа. Установите интервал не менее 24 часов")
            #         return redirect("item_list")

            try:
                check_plan_schedule_limitations(request.user.tenant, period, interval)
                schedule, created = IntervalSchedule.objects.get_or_create(
                    every=interval,
                    period=getattr(IntervalSchedule, period.upper()),  # IntervalSchedule.SECONDS, MINUTES, HOURS, etc
                )
            # This occurs when no interval value is set in the form
            except IntegrityError:
                messages.error(
                    request,
                    "Ошибка создания расписания. Убедитесь, что поле интервала заполнено.",
                )
                return redirect("item_list")

            # This occurs when no time unit is selected (e.g. minutes, hours, days).
            except AttributeError:
                messages.error(
                    request,
                    "Ошибка создания расписания. Убедитесь, что выбрана единица времени (например, часы, дни).",
                )
                return redirect("item_list")

            except PlanScheduleLimitationException as e:
                messages.error(request, e.message)
                return redirect("item_list")

            if created:
                logger.info(
                    "Interval created with schedule: every %s %s",
                    schedule.every,
                    schedule.period,
                )
            else:
                logger.info(
                    "Existing Interval started: every %s %s",
                    schedule.every,
                    schedule.period,
                )

            #  needs to be placed after all form checks to avoid updating quota despite the error
            if get_user_quota(request.user) is not None:
                try:
                    update_user_quota_for_allowed_parse_units(request.user, skus)
                except QuotaExceededException as e:
                    messages.error(request, e.message)
                    return redirect("item_list")

            scrape_interval_task, created = PeriodicTask.objects.update_or_create(
                name=task_name(request.user),
                defaults={
                    "interval": schedule,
                    "task": "main.tasks.update_or_create_items_task",
                    # "start_time": timezone.now(),
                    "last_run_at": timezone.now(),
                    "args": [request.user.tenant.id, skus_list],
                },
            )
            if created:
                logger.info(
                    "Interval task '%s' was successfully created for '%s'\nargs: %s",
                    scrape_interval_task.name,
                    request.user,
                    scrape_interval_task.args,
                )
            else:
                logger.info(
                    "Interval task '%s' was successfully updated for '%s'\nargs: %s",
                    scrape_interval_task.name,
                    request.user,
                    scrape_interval_task.args,
                )

            activate_parsing_for_selected_items(request, skus_list)

            return redirect("item_list")

    else:
        messages.error(
            request,
            "Что-то пошло не так. Попробуйте еще раз или обратитесь к администратору.",
        )
        scrape_interval_form = ScrapeIntervalForm(user=request.user)

    context = {"scrape_interval_form": scrape_interval_form}
    return render(request, "main/item_list.html", context)


def update_scrape_interval(request: WSGIRequest) -> HttpResponse:
    """Updates existing scrape interval for user's tenant and activates scraping for selected items.

    - Updates scrape interval based on form data.
    - Activates scraping for selected items (unchecks all first due to limitations).

    Args:
        request: The WSGI request object containing user and form data.

    Returns:
        - Redirects to item list on success.
        - Shows error message and re-renders form on failure.
    """
    existing_task = get_object_or_404(PeriodicTask, name=task_name(request.user))
    if request.method == "POST":
        form = ScrapeIntervalForm(request.POST or None, instance=existing_task, user=request.user)

        if form.is_valid():
            skus = request.POST.getlist("selected_items")
            if not skus:
                messages.error(
                    request,
                    'Не выбран ни один товар. Для удаления расписания кликните на "Удалить текущее"',
                )
                return redirect("item_list")
            skus_list = [int(sku) for sku in skus]

            uncheck_all_boxes(request)

            logger.info("Updating the checked items list for existing task...")
            existing_task.args = [request.user.tenant.id, skus_list]
            existing_task.save()
            form.save()

            activate_parsing_for_selected_items(request, skus_list)

            return redirect("item_list")
        else:
            messages.error(
                request,
                "Что-то пошло не так. Попробуйте еще раз или обратитесь к администратору.",
            )
            form = ScrapeIntervalForm(user=request.user)
    else:
        form = ScrapeIntervalForm(user=request.user)

    context = {"scrape_interval_form": form}
    return render(request, "main/item_list.html", context)


@user_passes_test(periodic_task_exists, redirect_field_name=None)
def destroy_scrape_interval_task(request: WSGIRequest) -> HttpResponseRedirect:
    uncheck_all_boxes(request)

    periodic_task = PeriodicTask.objects.get(
        name=task_name(request.user),
    )
    periodic_task.delete()
    print(f"{periodic_task} has been deleted!")

    return redirect("item_list")


def oferta_view(request: WSGIRequest) -> HttpResponse:
    return render(request, "main/oferta.html")


def superuser_or_test_modul(user) -> bool:
    return user.is_superuser or user.email == "test_modul@test.com"


class BillingView(UserPassesTestMixin, View):  # TODO: remove UserPassesTestMixin when fully implemented
    def test_func(self):
        return superuser_or_test_modul(self.request.user)

    def get(self, request):
        plan_name = request.GET.get(
            "plan", str(request.user.tenant.payment_plan.name)
        )  # Default is the user's current plan
        plan = get_object_or_404(PaymentPlan, name=plan_name)

        form = PaymentForm(
            initial={
                "terminal_key": "terminal_key",  # will be replaced with the actual value in POST
                # "amount": plan.price,  # Ensure amount is a string
                "client_email": request.user.tenant.name,
                # Other initial values as needed
            }
        )
        context = {"form": form, "plan": plan}
        # context = {"form": form, "plan": plan}
        if request.htmx:
            return render(request, "main/partials/payment_plan_modal.html", context)
        return render(request, "main/billing.html", context)

    def post(self, request):
        # plan_name = request.POST.get(
        #     "plan", str(request.user.tenant.payment_plan.name)
        # )  # Default is the user's current plan
        #
        # # Fetch the PaymentPlan object
        # plan = get_object_or_404(PaymentPlan, name=plan_name)
        # print(f"Plan POST: {plan}")
        form = PaymentForm(request.POST)
        # form.fields['terminal_key'] = settings.TINKOFF_TERMINAL_KEY_TEST

        if form.is_valid():
            amount = form.cleaned_data["amount"]
            try:
                order_id = create_unique_order_id(tenant_id=request.user.tenant.id)
            except ValueError as e:
                return HttpResponse(e, status=400)

            order, _ = Order.objects.get_or_create(
                tenant=request.user.tenant,
                order_id=order_id,
                defaults={
                    # "amount": float(plan.price),  # Convert to float for JSON serialization
                    "amount": float(amount),  # Convert to float for JSON serialization
                    # TODO: should be Order.OrderIntent.ADD_TO_BALANCE, and SWITCH_PLAN should be a separate view
                    # "order_intent": Order.OrderIntent.SWITCH_PLAN,
                    "order_intent": Order.OrderIntent.ADD_TO_BALANCE,
                },
            )

            # Prepare the receipt data
            receipt_data = {
                "EmailCompany": "info@mpmonitor.ru",
                "Taxation": "usn_income",
                "FfdVersion": "1.2",
                "Items": [
                    {
                        # "Name": f'Тариф "{plan.get_name_display()}"',
                        "Name": "Пополнение баланса",
                        # "Price": int(float(plan.price) * 100),  # Convert to integer (cents)
                        "Price": int(float(amount) * 100),
                        "Quantity": 1.00,
                        # "Amount": int(float(plan.price) * 100),  # Convert to integer (cents)
                        "Amount": int(float(amount) * 100),
                        "PaymentMethod": "full_payment",
                        "PaymentObject": "service",
                        "Tax": "none",  # none = без НДС
                        "MeasurementUnit": "pc",
                    }
                ],
                "Email": request.user.tenant.name,
            }

            # Construct the payload
            payload = {
                "TerminalKey": settings.TINKOFF_TERMINAL_KEY_TEST,  # Replace with your actual TerminalKey
                # "Amount": int(float(plan.price) * 100),  # Amount in cents
                "Amount": int(float(amount) * 100),
                "OrderId": order_id,
                "Email": request.user.tenant.name,
                # "Description": f'Payment for plan "{plan.get_name_display()}"',
                "Description": "Пополнение баланса",
                "Receipt": receipt_data,
                # Include other required fields as per Tinkoff's API documentation
            }

            logger.info("Generating token...")
            terminal_password = settings.TINKOFF_TERMINAL_PASSWORD_TEST
            generator = TinkoffTokenGenerator(terminal_password)
            token = generator.get_token(payload)
            logger.info("Adding token to payload...")
            payload["Token"] = token

            logger.info("Payload sent to Tinkoff.")
            headers = {"Content-Type": "application/json; charset=utf-8"}

            try:
                # Serialize payload with ensure_ascii=False to handle Cyrillic
                json_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
                response = requests.post("https://securepay.tinkoff.ru/v2/Init", data=json_payload, headers=headers)
                response.raise_for_status()  # Raise HTTPError for bad responses (4xx, 5xx)

                # Decode JSON response
                tinkoff_response = response.json()

                # Log the response with proper Cyrillic characters
                # logger.info("Tinkoff response: %s", json.dumps(tinkoff_response, ensure_ascii=False, indent=4))
                logger.info("Tinkoff responded successfully.")

            except requests.exceptions.RequestException as e:
                logger.exception("Error communicating with Tinkoff API: %s", e)
                return JsonResponse({"error": "Payment request failed"}, status=500)

            except json.JSONDecodeError as e:
                logger.exception("Error decoding Tinkoff API response %s", e)
                return JsonResponse({"error": "Failed to decode Tinkoff response"}, status=500)

            # Handle Tinkoff response
            if tinkoff_response.get("Success"):
                payment_url = tinkoff_response.get("PaymentURL")
                if payment_url and payment_url.startswith("https://securepayments.tinkoff.ru/"):
                    logger.info("Redirecting user to PaymentURL: %s", payment_url)
                    return redirect(payment_url)
                else:
                    logger.error("Invalid PaymentURL received: %s", payment_url)
                    return JsonResponse({"error": "Invalid payment URL"}, status=500)
            else:
                # Log the error details from Tinkoff
                logger.error(
                    "Payment initialization failed: %s", json.dumps(tinkoff_response, ensure_ascii=False, indent=4)
                )
                return JsonResponse(
                    {"error": "Payment initialization failed", "details": tinkoff_response},
                    json_dumps_params={"ensure_ascii": False},
                    status=400,
                )

        print(f"ERROR: Invalid payment form: {form.errors}")
        # context = {"form": form, "plan": plan}
        context = {"form": form}
        if request.htmx:
            return render(request, "main/partials/payment_plan_modal.html", context)
        return render(request, "main/billing.html", context)


@csrf_exempt
def payment_callback(request):  # TODO: remove this, if payment_callback_view works
    if request.method == "POST":
        try:
            # Parse the incoming JSON data
            data = json.loads(request.body)
            logger.info(f"Payment data: {data}")

            # token (Token) - howto: https://www.tbank.ru/kassa/dev/payments/#section/Token

            # Extract relevant information from the callback
            # create util funtion for it `validate_callback_data` (checking token, terminal_key, etc.)
            terminal_key = data.get("TerminalKey")
            order_id = data.get("OrderId")
            success = data.get("Success")  # True/False
            payment_status = data.get("Status")  # must be CONFIRMED
            payment_id = data.get("PaymentId")
            error_code = data.get("ErrorCode")  # must be 0
            amount = data.get("Amount")
            token = data.get("Token")  # noqa

            # Log the received data for debugging
            logger.info(
                f"Payment callback received: Success: {success}, ErrorCode: {error_code}, "
                f"TerminalKey: {terminal_key}, Status: {payment_status}, PaymentId: {payment_id}, "
                f"OrderId: {order_id}, Amount: {amount}"
            )

            # Print the data to the console (optional, for debugging during development)
            print(
                f"Payment callback received: Success: {success}, ErrorCode: {error_code}, "
                f"TerminalKey: {terminal_key}, Status: {payment_status}, PaymentId: {payment_id}, "
                f"OrderId: {order_id}, Amount: {amount}"
            )

            return JsonResponse({"status": "success"}, status=200)

        except Exception as e:
            logger.error(f"Error processing callback: {e}")
            return JsonResponse({"error": "Server error"}, status=500)

    return JsonResponse({"error": "Invalid method"}, status=405)


@csrf_exempt
def payment_callback_view(request: WSGIRequest) -> JsonResponse:
    if request.method == "POST":
        try:
            callback_data = json.loads(request.body)
            logger.info("Received payment callback")
        except json.JSONDecodeError as e:
            logger.error("JSON decode error: %s", e)
            return JsonResponse({"status": "invalid", "error": "Invalid JSON format"}, status=400)

        try:
            order = Order.objects.get(order_id=callback_data["OrderId"])
        except Order.DoesNotExist:
            return JsonResponse({"status": "invalid", "error": "Order not found"}, status=404)

        data_is_valid, error_message = validate_callback_data(callback_data, order)
        if data_is_valid:
            logger.info("Payment callback data validation successful. Updating payment records...")
            update_payment_records(data=callback_data, order=order)
            logger.info("Payment records updated successfully.")
            return JsonResponse({"status": "success"})
        else:
            logger.error("Payment callback data validation failed: %s", error_message)
            return JsonResponse({"status": "invalid"}, status=400)


@login_required
def switch_plan_modal(request):
    """
    Modal window for switching to a new payment plan.
    """
    new_plan = get_object_or_404(PaymentPlan, name=request.GET.get("plan"))
    current_plan = request.user.tenant.payment_plan

    # Get quotas from DEFAULT_QUOTAS
    current_quotas = config.DEFAULT_QUOTAS[current_plan.name]
    new_quotas = config.DEFAULT_QUOTAS[new_plan.name]
    price_per_parse = get_price_per_parse(current_plan.price, current_quotas["parse_units_limit"])

    context = {
        "current_plan": {
            "name": current_plan.get_name_display(),
            "price": current_plan.price,
            "skus_limit": current_quotas["skus_limit"],
            "parse_units_limit": current_quotas["parse_units_limit"],
            "price_per_parse": price_per_parse,
        },
        "new_plan": {
            "name": new_plan.get_name_display(),
            "price": new_plan.price,
            "skus_limit": new_quotas["skus_limit"],
            "parse_units_limit": new_quotas["parse_units_limit"],
            "price_per_parse": get_price_per_parse(new_plan.price, new_quotas["parse_units_limit"]),
        },
        "plan_id": new_plan.name,
    }

    return render(request, "main/partials/switch_plan_modal.html", context)


def switch_plan(request: WSGIRequest) -> HttpResponse:
    tenant = request.user.tenant
    if request.method == "POST":
        form = SwitchPlanForm(request.POST)
        if form.is_valid():
            new_plan = form.cleaned_data["plan"]
            if new_plan == tenant.payment_plan.name:
                messages.error(request, "Такой тариф уже выбран.")
                return redirect("billing")
            tenant.switch_plan(new_plan)
            messages.success(request, f"Тариф успешно переключен на {new_plan.get_name_display()}")
            return redirect("billing")
    else:
        return redirect("billing")

    # tenant = request.user.tenant
    # current_plan = tenant.payment_plan
    # if request.method == "POST":
    #     new_plan = request.POST.get("plan")
    #     tenant.switch_plan(new_plan)
    #     messages.success(request, f"Тариф успешно переключен на {new_plan.get_name_display()}")
    #     return redirect("billing")
    # else:
    #     context = {"current_plan": current_plan.get_name_display()}
    #     return render(request, "main/partials/switch_plan.html", context)

    # check if user has enough balance for at least 3 days (?) of payment
    # Determine what happens to excess resources if downgrading (i.e. if new plan doesn't allow so many parses, tell it to user and don't allow switch)
    # create appropriate OrderIntent (i.e. SWITCH_PLAN)
    # UX:
    # contents of modal windows (see "Create "Change plan" view" ticket in AFFiNe)
    # create notification that plan was successfully switched.
    # pass
