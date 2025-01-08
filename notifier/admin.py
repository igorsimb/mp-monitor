from django.contrib import admin

from notifier.models import PriceAlert


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    list_display = ("tenant", "get_items", "target_price", "target_price_direction", "is_active")
    list_editable = ("target_price", "target_price_direction", "is_active")
    list_filter = ("tenant",)

    @admin.display(description="items")
    def get_items(self, obj) -> str:
        return ", ".join([item.name for item in obj.items.all()])
