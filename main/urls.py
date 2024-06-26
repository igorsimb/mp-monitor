from django.urls import path

from .views import (
    index,
    ItemListView,
    ItemDetailView,
    create_scrape_interval_task,
    update_scrape_interval,
    destroy_scrape_interval_task,
    scrape_items,
    update_items,
    oferta_view,
)

urlpatterns = [
    path("", index, name="index"),
    path("item_list/", ItemListView.as_view(), name="item_list"),
    path("scrape_interval/", create_scrape_interval_task, name="create_scrape_interval"),
    path("update_scrape_interval/", update_scrape_interval, name="update_scrape_interval"),
    path(
        "destroy_scrape_interval/",
        destroy_scrape_interval_task,
        name="destroy_scrape_interval",
    ),
    # path("<str:username>/<str:slug>/", ItemDetailView.as_view(), name="item_detail"),
    path("items/<str:slug>/", ItemDetailView.as_view(), name="item_detail"),
    path("scrape/<str:skus>/", scrape_items, name="scrape_item"),
    path("update_items/", update_items, name="update_items"),
    path("oferta/", oferta_view, name="oferta"),
]
