from django.urls import path
from .views import ItemListView, ItemDetailView, scrape_items, trigger_print_task, destroy_print_task, \
    scrape_interval_task, destroy_scrape_interval_task

urlpatterns = [
    path('', ItemListView.as_view(), name='item_list'),
    path('print_task/', trigger_print_task, name='print_task'),
    path('destroy_task/', destroy_print_task, name='destroy_task'),
    path('scrape_interval/', scrape_interval_task, name='scrape_interval'),
    path('destroy_scrape_interval/', destroy_scrape_interval_task, name='destroy_scrape_interval'),
    path('<str:slug>/', ItemDetailView.as_view(), name='item_detail'),
    path('scrape/<str:skus>/', scrape_items, name='scraped_item'),
]
