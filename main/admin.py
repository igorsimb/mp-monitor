from django.contrib import admin

from main.models import Tenant, Product

class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price")

admin.site.register(Tenant)
admin.site.register(Product, ProductAdmin)
