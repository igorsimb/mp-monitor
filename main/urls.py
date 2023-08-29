from django.urls import path
from .views import ItemListView, ItemDetailView, scrape_items, create_scrape_interval_task, destroy_scrape_interval_task

urlpatterns = [
    path('', ItemListView.as_view(), name='item_list'),
    path('scrape_interval/', create_scrape_interval_task, name='create_scrape_interval'),
    path('destroy_scrape_interval/', destroy_scrape_interval_task, name='destroy_scrape_interval'),
    path('<str:slug>/', ItemDetailView.as_view(), name='item_detail'),
    path('scrape/<str:skus>/', scrape_items, name='scraped_item'),
]
