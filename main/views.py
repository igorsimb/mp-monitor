import re
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView
from guardian.mixins import PermissionListMixin, PermissionRequiredMixin

from .forms import ScrapeForm
from .models import Item, Price
from .scrape import get_scraped_data

user = get_user_model()


class ItemListView(PermissionListMixin, ListView):
    model = Item
    context_object_name = "items"
    permission_required = ["view_item"]
    template_name = "main/item_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = ScrapeForm()
        sku = None
        context["sku"] = sku
        context["form"] = form
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


# TODO: think how to scrape category
# TODO: think how to scrape image
# TODO: remove seller_name since it's the same as brand?
# TODO: add scrape_item to ListView's post method, or create a separate ItemCreateView:

# CreateView?
# https://github.com/django-guardian/django-guardian/blob/55beb9893310b243cbd6f578f9665c3e7c76bf96/example_project/articles/views.py#L19C1-L30C20
