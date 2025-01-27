import django_filters

from main.models import Item


class ItemFilter(django_filters.FilterSet):
    class Meta:
        model = Item
        fields = {"name": ["icontains"], "price": ["exact", "lt", "gt", "range"], "is_in_stock": ["exact"]}
