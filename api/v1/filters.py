import django_filters

from main.models import Item, Order


class ItemFilter(django_filters.FilterSet):
    class Meta:
        model = Item
        fields = {"name": ["icontains"], "price": ["exact", "lte", "gte", "range"], "is_in_stock": ["exact"]}


class OrderFilter(django_filters.FilterSet):
    # extract only the date component, not milliseconds etc. Useful for exact matches
    created_at = django_filters.DateFilter(field_name="created_at__date")

    class Meta:
        model = Order
        fields = {
            "amount": ["exact", "lte", "gte", "range"],
            "order_intent": ["exact"],
            "status": ["exact"],
            "created_at": ["lte", "gte", "exact"],
        }
