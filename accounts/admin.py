from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _
from simple_history.admin import SimpleHistoryAdmin

from accounts.forms import CustomUserCreationForm, CustomUserChangeForm
from accounts.models import User, TenantQuota, Tenant


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = User
    date_hierarchy = "created_at"
    list_display = ["email", "username", "created_at", "get_item_count", "is_demo_user", "is_active"]
    raw_id_fields = ["tenant"]
    list_filter = ["is_demo_user", "is_active"]
    list_display_links = [
        "email",
        "username",
    ]
    # Now we can see Tenant in create/change user panel
    fieldsets = (
        (None, {"fields": ("tenant", "username", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "email")}),
        (
            _("Permissions"),
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                ),
            },
        ),
        (_("Important dates"), {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("tenant", "username", "email", "password1", "password2"),
            },
        ),
    )

    @admin.display(description="SKU")  # same as get_item_sku.short_description = "SKU"
    def get_item_sku(self, obj) -> str:  # type: ignore
        return obj.item.sku  # pragma: no cover

    # number of items for a user
    @admin.display(description="Товаров")
    def get_item_count(self, obj) -> str:
        return obj.tenant.item_set.count()


class TenantInline(admin.TabularInline):
    model = Tenant
    extra = 0


@admin.register(TenantQuota)
class TenantQuotaAdmin(admin.ModelAdmin):
    model = TenantQuota
    inlines = [TenantInline]
    list_display = [
        "name",
        "total_hours_allowed",
        "skus_limit",
        "manual_updates_limit",
        "scheduled_updates_limit",
        "parse_units_limit",
    ]
    list_display_links = ["name", "total_hours_allowed"]


@admin.register(Tenant)
class TenantAdmin(SimpleHistoryAdmin):
    history_list_display = ["tenant_status"]
    list_display = ["name", "status", "payment_plan", "quota"]

    def tenant_status(self, obj):
        return obj.get_status_display()


admin.site.unregister(EmailAddress)
