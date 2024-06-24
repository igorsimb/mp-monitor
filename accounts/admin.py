from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from allauth.account.models import EmailAddress
from django.utils.translation import gettext_lazy as _

from accounts.forms import CustomUserCreationForm, CustomUserChangeForm
from accounts.models import CustomUser, UserQuota


class QuotaInline(admin.TabularInline):
    model = UserQuota
    extra = 0


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    inlines = [QuotaInline]
    add_form = CustomUserCreationForm
    form = CustomUserChangeForm
    model = CustomUser
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


@admin.register(UserQuota)
class UserQuotaAdmin(admin.ModelAdmin):
    model = UserQuota
    list_display = ["user", "user_lifetime_hours", "max_allowed_skus", "manual_updates", "scheduled_updates"]
    raw_id_fields = ["user"]


admin.site.unregister(EmailAddress)
