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
    # billing_view,
    payment_callback_view,
    # create_payment,
    # payment_success,
    load_chart,
    BillingView,
    switch_plan_view,
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
    path("items/<str:slug>/", ItemDetailView.as_view(), name="item_detail"),
    path("scrape/<str:skus>/", scrape_items, name="scrape_item"),
    path("update_items/", update_items, name="update_items"),
    path("oferta/", oferta_view, name="oferta"),
    # path("billing/", billing_view, name="billing"),
    path("billing/", BillingView.as_view(), name="billing"),
    # path("billing/payment/", create_payment, name="payment"),
    # path("billing/payment-success/", payment_success, name="payment_success"),
    path("load-chart/<str:sku>/", load_chart, name="load_chart"),
    # payment callback (to be created)
    path("payment/callback/", payment_callback_view, name="payment_callback"),
    path("billing/switch-plan/", switch_plan_view, name="switch_plan"),
]
