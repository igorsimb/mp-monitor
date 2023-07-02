import httpx
from django.contrib.auth import get_user_model
from django.shortcuts import render
from django.views.generic import ListView
from guardian.mixins import PermissionListMixin

from main.models import Item

user = get_user_model()


class ItemListView(PermissionListMixin, ListView):
    model = Item
    context_object_name = "items"
    permission_required = ["main.view_item"]
    template_name = "main/item_list.html"


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
    # item is a list, not a dictionary
    # To avoid error "'list' object has no attribute 'get'", we access the first item in the list
    if item:
        item = item[0]

    # Extracting the scraped data
    name = item.get('name', None)
    price = float(item.get('salePriceU', None)) / 100 \
                if item.get('salePriceU', None) is not None else None
    price_without_discount = float(item.get('PriceU', None)) / 100 \
        if item.get('PriceU', None) is not None else None
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
    item, created = Item.objects.get_or_create(
        tenant=tenant,
        name=name,
        sku=sku,
        price=price,
        price_without_discount=price_without_discount,
        image=image,
        category=category,
        brand=brand,
        seller_name=seller_name,
        rating=rating,
        num_reviews=num_reviews,

    )

    item.save()

    context = {"item": item}

    # TODO: replace with item_list redirect when item_detail is ready, ie: return redirect("item_list")
    return render(request, "main/scrape_item.html", context)
