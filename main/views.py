import logging
import re

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.generic import ListView, DetailView
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from guardian.mixins import PermissionListMixin, PermissionRequiredMixin

from .forms import ScrapeForm, ScrapeIntervalForm
from .models import Item, Price
from .utils import get_scraped_data

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

        return context

    def get(self, request, *args, **kwargs):
        logger.info("Going to Details Page for item SKU '%s' (%s)", self.get_object().sku, self.get_object().name)
        return super().get(request, *args, **kwargs)


def scrape_items(request, skus):
    if request.method == "POST":
        form = ScrapeForm(request.POST)
        if form.is_valid():
            skus = form.cleaned_data["skus"]

            items_data = []
            # the regex accepts the following formats for skus:
            # - separated by comma with our without space in-between
            # - separated by space
            # - separated by new line
            # - combination of the above
            # e.g. 141540568, 13742696,20904017 3048451
            for sku in re.split(r"\s+|\n|,(?:\s*)", skus):
                item_data = get_scraped_data(sku)
                items_data.append(item_data)

            for item_data in items_data:
                item, created = Item.objects.update_or_create(
                    tenant=request.user.tenant,
                    sku=item_data["sku"],
                    defaults=item_data,
                )

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

        interval = scrape_interval_form.cleaned_data["interval"]
        selected_item_ids = request.POST.getlist("selected_items")
        print(f"{selected_item_ids=}")
        items_to_parse = Item.objects.filter(Q(tenant=request.user.tenant.id) & Q(id__in=selected_item_ids))
        print(f"{items_to_parse=}")

        if scrape_interval_form.is_valid():
            schedule, created = IntervalSchedule.objects.get_or_create(
                every=interval,
                period=IntervalSchedule.SECONDS,
            )

            scrape_interval_task = PeriodicTask.objects.create(
                interval=schedule,
                name=f"scrape_interval_task_{request.user}",
                task="main.tasks.scrape_interval_task",
                start_time=timezone.now(),  # trigger once right away and then keep the interval
                # args=[request.user.tenant.id],
                args=[request.user.tenant.id, items_to_parse],
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


def destroy_scrape_interval_task(request):
    periodic_task = PeriodicTask.objects.get(name=f"scrape_interval_task_{request.user}")
    periodic_task.delete()
    print(f"{periodic_task} has been deleted!")

    # delete 'scrape_interval_task' from session
    if "scrape_interval_task" in request.session:
        del request.session["scrape_interval_task"]

    return redirect("item_list")


# TODO: checkboxes for each item + checkbox to "choose all"
# TODO: tests
# TODO: dockerize everything!
