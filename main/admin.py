from django.contrib import admin

from main.models import Tenant, Item

class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price")

admin.site.register(Tenant)
admin.site.register(Item, ItemAdmin)
