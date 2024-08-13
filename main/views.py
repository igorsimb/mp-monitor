import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test, login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models.query import QuerySet
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.generic import ListView, DetailView
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from django_ratelimit.core import is_ratelimited
from guardian.mixins import PermissionListMixin, PermissionRequiredMixin

import config
from .exceptions import QuotaExceededException
from .forms import ScrapeForm, ScrapeIntervalForm, UpdateItemsForm
from .models import Item, Price
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
)

user = get_user_model()
logger = logging.getLogger(__name__)


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

        context["prices"] = prices_paginated
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

            try:
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


@login_required
def billing_view(request: WSGIRequest) -> HttpResponse:
    return render(request, "main/billing.html")


# TODO:
#   - billing page: display current balance (if user paid 5k, it should display 5k)
#   - add balance field to Tenant model
