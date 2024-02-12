import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.handlers.wsgi import WSGIRequest
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
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
        sku = None
        context["sku"] = sku
        context["form"] = form
        context["update_items_form"] = update_items_form
        context["scrape_interval_form"] = scrape_interval_form
        context["scrape_interval_task"] = self.request.session.get("scrape_interval_task")
        return context

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

    def get(self, request, *args, **kwargs):
        logger.info("Going to Details Page for item SKU '%s' (%s)", self.get_object().sku, self.get_object().name)
        return super().get(request, *args, **kwargs)


def scrape_items(request: WSGIRequest, skus: str) -> HttpResponse | HttpResponseRedirect:
    if request.method == "POST":
        form = ScrapeForm(request.POST)
        if form.is_valid():
            skus = form.cleaned_data["skus"]
            logger.info("Scraping items with SKUs: %s", skus)
            items_data = scrape_items_from_skus(skus)
            update_or_create_items(request, items_data)
            show_successful_scrape_message(request, items_data, max_items_on_screen=10)

            return redirect("item_list")
    else:
        form = ScrapeForm()
    return render(request, "main/item_list.html", {"form": form})


def update_items(request: WSGIRequest) -> HttpResponse | HttpResponseRedirect:
    if request.method == "POST":
        form = UpdateItemsForm(request.POST)
        if form.is_valid():
            skus = request.POST.getlist("selected_items")
            # Convert the list of stringified numbers to a string of integers for scrape_items_from_skus:
            skus = " ".join(skus)
            logger.info("Beginning to update items info...")
            if not is_at_least_one_item_selected(request, skus):
                return redirect("item_list")

            uncheck_all_boxes(request)

            items_data = scrape_items_from_skus(skus)
            update_or_create_items(request, items_data)
            show_successful_scrape_message(request, items_data, max_items_on_screen=10)

            return redirect("item_list")
        else:
            logger.error("Form is invalid. %s", form.errors)
            messages.error(request, "Что-то пошло не так. Попробуйте еще раз или обратитесь к администратору.")
            return redirect("item_list")
    else:
        form = UpdateItemsForm()
    return render(request, "main/item_list.html", {"update_items_form": form})


# TODO: remove this if the new create_scrape_interval_task view works fine
def create_scrape_interval_task_old(request: WSGIRequest) -> HttpResponse | HttpResponseRedirect:
    """Takes interval from the form data (in seconds) and triggers main.tasks.scrape_interval_task

    The task itself prints all items belonging to this tenant every {{ interval }} seconds.
    """

    if request.method == "POST":
        scrape_interval_form = ScrapeIntervalForm(request.POST)

        if scrape_interval_form.is_valid():
            logger.info("Starting the task")
            selected_item_ids = request.POST.getlist("selected_items")

            if not is_at_least_one_item_selected(request, selected_item_ids):
                return redirect("item_list")

            uncheck_all_boxes(request)

            # Update the database for checked boxes
            for item_id in selected_item_ids:
                logger.info("Updating db with item with id=%s", item_id)
                Item.objects.filter(id=int(item_id)).update(is_parser_active=True)

            # Convert the list of stringified numbers to a list of integers to avoid the following error:
            # json.decoder.JSONDecodeError: Expecting value: line 1 column 6 (char 5)
            selected_item_ids = [int(item) for item in selected_item_ids]

            interval = scrape_interval_form.cleaned_data["interval"]
            print(f"{interval=}")
            print(f'"{request.user.tenant.id=}"')
            schedule, created = IntervalSchedule.objects.get_or_create(
                every=interval,
                period=IntervalSchedule.SECONDS,
            )
            if created:
                logger.debug("Interval created with schedule: every %s %s", schedule.every, schedule.period)
            else:
                logger.debug("Existing Interval started: every %s %s", schedule.every, schedule.period)

            scrape_interval_task = PeriodicTask.objects.create(
                interval=schedule,
                name=f"scrape_interval_task_{request.user}",
                task="main.tasks.scrape_interval_task",
                start_time=timezone.now(),  # trigger once right away and then keep the interval
                args=[request.user.tenant.id, selected_item_ids],
            )
            logger.debug(
                "Interval task '%s' was successfully created for '%s'", scrape_interval_task.name, request.user
            )

            # store 'scrape_interval_task' in session to display as context in item_list.html
            request.session["scrape_interval_task"] = f"{scrape_interval_task.name} - {scrape_interval_task.interval}"

            return redirect("item_list")

    else:
        scrape_interval_form = ScrapeIntervalForm()

    context = {
        "scrape_interval_form": scrape_interval_form,
        "scrape_interval_task": request.session.get("scrape_interval_task"),
    }
    return render(request, "main/item_list.html", context)


def create_scrape_interval_task(request: WSGIRequest) -> HttpResponse | HttpResponseRedirect:
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
            schedule, created = IntervalSchedule.objects.get_or_create(
                every=interval,
                period=IntervalSchedule.SECONDS,
            )
            if created:
                logger.info("Interval created with schedule: every %s %s", schedule.every, schedule.period)
            else:
                logger.info("Existing Interval started: every %s %s", schedule.every, schedule.period)

            scrape_interval_task = PeriodicTask.objects.create(
                interval=schedule,
                name=f"scrape_interval_task_{request.user}",
                task="main.tasks.update_or_create_items_task",
                # start_time=timezone.now(),  # trigger once right away and then keep the interval
                args=[request.user.tenant.id, skus_list],  # prolly don't need request, just skus_list
            )
            logger.info(
                "Interval task '%s' was successfully created for '%s'\nargs: %s",
                scrape_interval_task.name,
                request.user,
                scrape_interval_task.args,
            )

            # store 'scrape_interval_task' in session to display as context in item_list.html
            request.session["scrape_interval_task"] = f"{scrape_interval_task.name} - {scrape_interval_task.interval}"

            # Set the selected items' field "is_parser_active" to True
            items = Item.objects.filter(Q(tenant_id=request.user.tenant.id) & Q(sku__in=skus_list))
            items_bulk_update_list = []
            for item in items:
                item.is_parser_active = True
                items_bulk_update_list.append(item)
            Item.objects.bulk_update(items_bulk_update_list, ["is_parser_active"])

            return redirect("item_list")

    else:
        messages.error(request, "Что-то пошло не так. Попробуйте еще раз или обратитесь к администратору.")
        scrape_interval_form = ScrapeIntervalForm()

    context = {
        "scrape_interval_form": scrape_interval_form,
        "scrape_interval_task": request.session.get("scrape_interval_task"),
    }
    return render(request, "main/item_list.html", context)


def destroy_scrape_interval_task(request: WSGIRequest) -> HttpResponseRedirect:
    uncheck_all_boxes(request)

    periodic_task = PeriodicTask.objects.get(name=f"scrape_interval_task_{request.user}")
    periodic_task.delete()
    print(f"{periodic_task} has been deleted!")

    # delete 'scrape_interval_task' from session
    if "scrape_interval_task" in request.session:
        del request.session["scrape_interval_task"]

    return redirect("item_list")
