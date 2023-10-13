import logging
import re

from django.contrib.auth import get_user_model
from django.core.handlers.wsgi import WSGIRequest
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.generic import ListView, DetailView
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from guardian.mixins import PermissionListMixin, PermissionRequiredMixin

from .forms import ScrapeForm, ScrapeIntervalForm
from .models import Item, Price
from .utils import scrape_item, uncheck_all_boxes, show_successful_scrape_message, is_at_least_one_item_selected

user = get_user_model()
logger = logging.getLogger(__name__)


class ItemListView(PermissionListMixin, ListView):
    model = Item
    context_object_name = "items"
    permission_required = ["view_item"]
    template_name = "main/item_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = ScrapeForm()
        scrape_interval_form = ScrapeIntervalForm()
        sku = None
        context["sku"] = sku
        context["form"] = form
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        prices = Price.objects.filter(item=self.object)
        context["prices"] = prices

        # Add bootstrap table classes based on price comparison
        # https://getbootstrap.com/docs/5.3/content/tables/#variants
        for i in range(len(prices)):
            try:
                if prices[i].value < prices[i + 1].value:
                    prices[i].table_class = "table-danger"
                    prices[i].trend = "↓"
                elif prices[i].value > prices[i + 1].value:
                    prices[i].table_class = "table-success"
                    prices[i].trend = "↑"
                else:
                    prices[i].table_class = "table-warning"
                    prices[i].trend = "="

            # the original price is the last price in the list, so no comparison is possible
            except IndexError:
                prices[i].table_class = ""
            except TypeError:
                logger.warning("Can't compare price to NoneType")

        return context

    def get(self, request, *args, **kwargs):
        logger.info("Going to Details Page for item SKU '%s' (%s)", self.get_object().sku, self.get_object().name)
        return super().get(request, *args, **kwargs)


def scrape_items(request, skus: str) -> HttpResponse | HttpResponseRedirect:
    if request.method == "POST":
        form = ScrapeForm(request.POST)
        if form.is_valid():
            skus = form.cleaned_data["skus"]
            logger.info("Going to scrape items: %s", skus)

            items_data = []
            # the regex accepts the following formats for skus:
            # - separated by comma with our without space in-between
            # - separated by space
            # - separated by new line
            # - combination of the above
            # e.g. 141540568, 13742696,20904017 3048451
            for sku in re.split(r"\s+|\n|,(?:\s*)", skus):
                logger.info("Scraping item: %s", sku)
                item_data = scrape_item(sku)
                items_data.append(item_data)

            logger.info("Checking for items_data: %s", items_data)
            for item_data in items_data:
                item, created = Item.objects.update_or_create(  # pylint: disable=unused-variable
                    tenant=request.user.tenant,
                    sku=item_data["sku"],
                    defaults=item_data,
                )

            show_successful_scrape_message(request, items_data, max_items_on_screen=10)

            return redirect("item_list")
    else:
        form = ScrapeForm()
    return render(request, "main/item_list.html", {"form": form})


def create_scrape_interval_task(request):
    """
    Takes interval from the form data (in seconds) and triggers main.tasks.scrape_interval_task
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
                Item.objects.filter(id=int(item_id)).update(is_parser_active=True)

            # Convert the list of stringified numbers to a list of integers to avoid the following error:
            # json.decoder.JSONDecodeError: Expecting value: line 1 column 6 (char 5)
            selected_item_ids = [int(item) for item in selected_item_ids]
            print(f"{selected_item_ids=}")

            interval = scrape_interval_form.cleaned_data["interval"]
            print(f"{interval=}")
            print(f'"{request.user.tenant.id=}"')
            schedule, created = IntervalSchedule.objects.get_or_create(  # pylint: disable=unused-variable
                every=interval,
                period=IntervalSchedule.SECONDS,
            )
            if created:
                logger.debug("Interval created with schedule: every %s %s", schedule.every, schedule.period)
            else:
                logger.error("Something went wrong. Interval was not created!")

            kwargs_str = {"tenant_id": "1", "selected_item_ids_json": " + json.dumps(str(selected_item_ids)) + "}
            print(f"{kwargs_str=}")

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


def destroy_scrape_interval_task(request: WSGIRequest) -> HttpResponseRedirect:
    uncheck_all_boxes(request)

    periodic_task = PeriodicTask.objects.get(name=f"scrape_interval_task_{request.user}")
    periodic_task.delete()
    print(f"{periodic_task} has been deleted!")

    # delete 'scrape_interval_task' from session
    if "scrape_interval_task" in request.session:
        del request.session["scrape_interval_task"]

    return redirect("item_list")
