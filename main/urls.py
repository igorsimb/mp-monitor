from django.urls import path
from .views import ItemListView, scrape_item

urlpatterns = [
    path('', ItemListView.as_view(), name='item_list'),
    path('<str:sku>/', scrape_item, name='scraped_item'),
]