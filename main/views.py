import re
from datetime import timedelta, datetime

from celery import current_app
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView
from guardian.mixins import PermissionListMixin, PermissionRequiredMixin

from django_celery_beat.models import PeriodicTask, IntervalSchedule

from mp_monitor.celery import app
from .forms import ScrapeForm, TaskForm, ScrapeIntervalForm
from .models import Item, Price, Printer
from .scrape import get_scraped_data
from .tasks import print_task

from django.utils import timezone

user = get_user_model()


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
        context["scrape_interval_task"] = self.request.session.get('scrape_interval_task')
        return context


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
                    prices[i].table_class = 'table-danger'
                    prices[i].trend = '↓'
                elif prices[i].value > prices[i + 1].value:
                    prices[i].table_class = 'table-success'
                    prices[i].trend = '↑'
                else:
                    prices[i].table_class = 'table-warning'
                    prices[i].trend = '='
            # the original price is the last price in the list, so no comparison is possible
            except IndexError:
                prices[i].table_class = ''

        return context


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


def trigger_print_task(request):
    task_date = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
    # task = 'hello'
    printers =  Printer.objects.all()
    if request.method == "POST":
        task_form = TaskForm(request.POST)
        if task_form.is_valid():
            interval = task_form.cleaned_data["interval"]

            schedule, created = IntervalSchedule.objects.get_or_create(
            every = interval,
            period = IntervalSchedule.SECONDS,
            )

            task = PeriodicTask.objects.create(
                interval=schedule,
                name=f'task_{request.user}',
                task='main.tasks.print_task',
                # expires=datetime.now() + timedelta(seconds=30)
            )
            # task.save()

            # store 'task' in session to display as context in print_task.html
            request.session['task'] = f'{task.name} - {task.interval}'

            # To stop task
            # periodic_task = PeriodicTask.objects.get(name='task_name')
            # periodic_task.enabled = False
            # periodic_task.save()


                # print_task.apply_async(countdown=interval)

            # task = current_app.send_task('main.tasks.print_task')
            # print_task.apply_async(countdown=interval, repeat=True)
            # #

            return redirect("print_task")

            # context = {
            #     'task_form': task_form,
            #     'printers': printers,
            #     'task': task,
            # }
            # return render(request, "main/print_task.html", context)
    else:
        task_form = TaskForm()

    context = {
        'task_form': task_form,
        'printers': printers,
        'task':  request.session.get('task'),
    }
    return render(request, "main/print_task.html", context)

def destroy_print_task(request):
    # if request.method == "POST":
    #     task_form = TaskForm(request.POST)
    #     if task_form.is_valid():
    # interval = task_form.cleaned_data["interval"]

    periodic_task = PeriodicTask.objects.get(name=f'task_{request.user}')
    # periodic_task.enabled = False
    # periodic_task.save()
    periodic_task.delete()
    print(f"{periodic_task} has been deleted!")

    # delete 'task' from session
    if 'task' in request.session:
        del request.session['task']

    return redirect("print_task")


def scrape_interval_task(request):
    """
    Takes interval from the form data (in seconds) and triggers main.tasks.scrape_interval_task
    The task itself prints all items belonging to this tenant every {{ interval }} seconds.
    """
    # task_date = datetime.now().strftime('%Y-%m-%d_%H:%M:%S')
    # # task = 'hello'
    # items = Item.objects.filter(tenant=request.user.tenant)
    # items_skus = [item.sku for item in items]
    # print(f"{items_skus=}")

    if request.method == "POST":
        scrape_interval_form = ScrapeIntervalForm(request.POST)
        if scrape_interval_form.is_valid():
            interval = scrape_interval_form.cleaned_data["interval"]

            schedule, created = IntervalSchedule.objects.get_or_create(
            every = interval,
            period = IntervalSchedule.SECONDS,
            )

            scrape_interval_task = PeriodicTask.objects.create(
                interval=schedule,
                name=f'scrape_interval_task_{request.user}',
                task='main.tasks.scrape_interval_task',
                start_time=timezone.now(), # trigger once right away and then keep the interval
                args=[request.user.tenant.id],
            )

            # store 'scrape_interval_task' in session to display as context in print_task.html
            request.session['scrape_interval_task'] = f'{scrape_interval_task.name} - {scrape_interval_task.interval}'

            return redirect("item_list")

    else:
        scrape_interval_form = ScrapeIntervalForm()

    context = {
        'scrape_interval_form': scrape_interval_form,
        'scrape_interval_task':  request.session.get('scrape_interval_task'),
    }
    return render(request, "main/item_list.html", context)

def destroy_scrape_interval_task(request):
    # if request.method == "POST":
    #     task_form = TaskForm(request.POST)
    #     if task_form.is_valid():
    # interval = task_form.cleaned_data["interval"]

    periodic_task = PeriodicTask.objects.get(name=f'scrape_interval_task_{request.user}')
    # periodic_task.enabled = False
    # periodic_task.save()
    periodic_task.delete()
    print(f"{periodic_task} has been deleted!")

    # delete 'task' from session
    if 'scrape_interval_task' in request.session:
        del request.session['scrape_interval_task']

    return redirect("item_list")





# TODO: think how to scrape category
# TODO: think how to scrape image
# TODO: remove seller_name since it's the same as brand?
# TODO: add scrape_item to ListView's post method, or create a separate ItemCreateView:

# CreateView?
# https://github.com/django-guardian/django-guardian/blob/55beb9893310b243cbd6f578f9665c3e7c76bf96/example_project/articles/views.py#L19C1-L30C20
