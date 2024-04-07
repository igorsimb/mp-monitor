import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import user_passes_test
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models.query import QuerySet
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView, TemplateView
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from guardian.mixins import PermissionListMixin, PermissionRequiredMixin

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
)

user = get_user_model()
logger = logging.getLogger(__name__)


class IndexView(TemplateView):
    """The entry point for the website."""

    template_name = "main/index.html"


class ItemListView(PermissionListMixin, ListView):
    # TODO: add min/max pills if min or max
    model = Item
    context_object_name = "items"
    permission_required = ["view_item"]
    template_name = "main/item_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        form = ScrapeForm()
        update_items_form = UpdateItemsForm()
        scrape_interval_form = ScrapeIntervalForm()

        try:
            periodic_task = PeriodicTask.objects.get(name=task_name(self.request.user))
        except PeriodicTask.DoesNotExist:
            periodic_task = None

        sku = None
        context["sku"] = sku
        context["form"] = form
        context["update_items_form"] = update_items_form
        context["scrape_interval_form"] = scrape_interval_form
        if periodic_task:
            context["scrape_interval_task"] = periodic_task.interval
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
        items_per_page = 10
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

        context["prices"] = prices_paginated
        context["item_updated_at"] = item_updated_at
        context["price_created_at"] = price_created_at
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


def scrape_items(request: WSGIRequest, skus: str) -> HttpResponse | HttpResponseRedirect:
    if request.method == "POST":
        form = ScrapeForm(request.POST)
        if form.is_valid():
            skus = form.cleaned_data["skus"]
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
    """Scrape items manually"""
    if request.method == "POST":
        form = UpdateItemsForm(request.POST)
        if form.is_valid():
            skus = request.POST.getlist("selected_items")
            # Convert the list of stringified numbers to a string of integers for scrape_items_from_skus:
            skus = " ".join(skus)
            logger.info("Beginning to update items info...")
            if not is_at_least_one_item_selected(request, skus):
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
        scrape_interval_form = ScrapeIntervalForm(request.POST)

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
            period = scrape_interval_form.cleaned_data["period"].upper()

            try:
                schedule, created = IntervalSchedule.objects.get_or_create(
                    every=interval,
                    period=getattr(IntervalSchedule, period),  # IntervalSchedule.SECONDS, MINUTES, HOURS, etc
                )

            # This occurs when no interval value is set in the form
            except IntegrityError:
                messages.error(
                    request,
                    "Ошибка создания расписания. Убедитесь, что поле интервала заполнено.",
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

            scrape_interval_task, created = PeriodicTask.objects.update_or_create(
                name=task_name(request.user),
                defaults={
                    "interval": schedule,
                    "task": "main.tasks.update_or_create_items_task",
                    # "start_time": timezone.now(),
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
        scrape_interval_form = ScrapeIntervalForm()

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
        form = ScrapeIntervalForm(request.POST or None, instance=existing_task)

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
            form = ScrapeIntervalForm()
    else:
        form = ScrapeIntervalForm()

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
