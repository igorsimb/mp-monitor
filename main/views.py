import httpx
from django.contrib.auth import get_user_model
from django.shortcuts import render, redirect
from django.views.generic import ListView, DetailView
from guardian.mixins import PermissionListMixin, PermissionRequiredMixin

from main.models import Item, Price

user = get_user_model()


class ItemListView(PermissionListMixin, ListView):
    model = Item
    context_object_name = "items"
    permission_required = ["view_item"]
    template_name = "main/item_list.html"


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


def scrape_item(request, sku, **kwargs):
    # Scraping the item and extracting relevant information
    url = f'https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={sku}'

    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9,ms;q=0.8",
        "Connection": "keep-alive",
        "Origin": "https://www.wildberries.ru",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "cross-site",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/000000000 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": "Windows",
    }

    with httpx.Client() as client:
        response = client.get(url, headers=headers)
        data = response.json()

    item = data.get('data', {}).get("products", None)
    print(f"IGOR0 {item=}")
    # item is a list, not a dictionary
    # To avoid error "'list' object has no attribute 'get'", we access the first item in the list
    if item:
        item = item[0]

    print(f"IGOR1 {item=}")

    # Extracting the scraped data
    name = item.get('name', None)
    sku = item.get('id', None)
    price = float(item.get('salePriceU', None)) / 100 \
                if item.get('salePriceU', None) is not None else None
    # TODO: image needs to go from elsewhere
    image = item.get('image', None)
    # TODO: category needs to go from eslewhere (right now it's = brand)
    category = item.get('category', None)
    brand = item.get('brand', None)
    seller_name = item.get('brand', None)
    rating = float(item.get('rating', None))
    num_reviews = int(item.get('feedbacks', None))

    # Populating the Item model with the scraped data
    tenant = request.user.tenant
    updated_values = {
        'name': name,
        'price': price,
        'image': image,
        'category': category,
        'brand': brand,
        'seller_name': seller_name,
        'rating': rating,
        'num_reviews': num_reviews,
    }

    # update_or_create looks at tenant and sku, and if exist in db, uses defaults to update values
    # source: https://thetldr.tech/when-to-use-update_or_create-in-django/
    item, created = Item.objects.update_or_create(
        tenant=tenant,
        sku=sku,
        defaults=updated_values
    )

    item.save()
    return redirect("item_list")


# TODO: think how to scrape category
# TODO: think how to scrape image
# TODO: remove seller_name since it's the same as brand?