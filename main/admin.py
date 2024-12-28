from django.contrib import admin

from accounts.models import PaymentPlan
from main.models import Item, Price, Payment, Order


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price", "tenant", "is_in_stock", "is_parser_active", "is_notifier_active")
    list_editable = ("is_parser_active", "is_notifier_active")


@admin.register(Price)
class PriceAdmin(admin.ModelAdmin):
    list_display = ("get_item_sku", "get_item_name", "value", "created_at")
    list_editable = ("value",)
    search_fields = ("item__name", "item__sku")

    @admin.display(description="SKU")  # same as get_item_sku.short_description = "SKU"
    def get_item_sku(self, obj) -> str:  # type: ignore
        return obj.item.sku

    @admin.display(description="Товар")
    def get_item_name(self, obj) -> str:  # type: ignore
        return obj.item.name


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("tenant", "order_id", "amount", "status", "order_intent", "created_at")
    search_fields = ("tenant", "order_id")
    search_help_text = "Search by tenant or order ID"


admin.site.register(PaymentPlan)
admin.site.register(Payment)
