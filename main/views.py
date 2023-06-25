from django.views.generic import ListView, DetailView
from django.contrib.auth import get_user_model
from guardian.mixins import PermissionListMixin, PermissionRequiredMixin

from main.models import Product

User = get_user_model()


class ProductListView(PermissionListMixin, ListView):
    model = Product
    context_object_name = "products"
    permission_required = ["main.view_product"]
    template_name = "main/product_list.html"
