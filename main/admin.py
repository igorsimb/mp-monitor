from django.contrib import admin

from main.models import Tenant, Item, Price

class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price")

class PriceAdmin(admin.ModelAdmin):
    list_display = ("item", "value", "date_added")
    list_editable = ("value",)

admin.site.register(Tenant)
admin.site.register(Item, ItemAdmin)
admin.site.register(Price, PriceAdmin)
