from django.urls import path
from .views import ProductListView, scrape_item

urlpatterns = [
    path('', ProductListView.as_view(), name='product-list'),
    path('<str:sku>/', scrape_item, name='product'),
]