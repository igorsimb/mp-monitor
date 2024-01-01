from django.contrib import admin

from main.models import Tenant, Item, Price


class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price", "tenant", "is_parser_active")
    list_editable = ("is_parser_active",)


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


admin.site.register(Tenant)
admin.site.register(Item, ItemAdmin)
admin.site.register(Price, PriceAdmin)
