from django.urls import path
from .views import ItemListView, ItemDetailView, scrape_items

urlpatterns = [
    path('', ItemListView.as_view(), name='item_list'),
    path('<str:slug>/', ItemDetailView.as_view(), name='item_detail'),
    path('scrape/<str:skus>/', scrape_items, name='scraped_item'),
]