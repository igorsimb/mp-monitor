from django.urls import path
from .views import ItemListView, ItemDetailView, scrape_item

urlpatterns = [
    path('', ItemListView.as_view(), name='item_list'),
    path('<str:slug>/', ItemDetailView.as_view(), name='item_detail'),
    path('scrape/<str:sku>/', scrape_item, name='scraped_item'),
]