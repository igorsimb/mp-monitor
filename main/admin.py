from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

# from accounts.models import Tenant
from main.models import Item, Price, PaymentPlan


# class TenantQuotaInline(admin.TabularInline):
#     model = TenantQuota
#     extra = 0


# @admin.register(Tenant)
# class TenantAdmin(SimpleHistoryAdmin):
#     history_list_display = ["tenant_status"]
#     list_display = ["name", "status", "payment_plan", "quota"]
#
#     def tenant_status(self, obj):
#         return obj.get_status_display()


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = ("sku", "name", "price", "tenant", "is_in_stock", "is_parser_active")
    list_editable = ("is_parser_active",)


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


admin.site.register(PaymentPlan)
