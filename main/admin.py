from django.contrib import admin

from main.models import Tenant, Item, Price, Printer


class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price", "tenant")

class PriceAdmin(admin.ModelAdmin):
    list_display = ("get_item_sku", "get_item_name", "value", "date_added")
    list_editable = ("value",)
    search_fields = ("item__name", "item__sku")

    @admin.display(description="SKU") # same as get_item_sku.short_description = "SKU"
    def get_item_sku(self, obj):
        return obj.item.sku

    @admin.display(description="Товар")
    def get_item_name(self, obj):
        return obj.item.name


class PrinterAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "created_at")

admin.site.register(Tenant)
admin.site.register(Item, ItemAdmin)
admin.site.register(Price, PriceAdmin)
admin.site.register(Printer, PrinterAdmin)
