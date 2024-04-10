from django.contrib import admin
from django.urls import path, include

from accounts.views import logout_view

urlpatterns = [
    # Django admin
    path("definitely-not-admin/", admin.site.urls),
    # User management
    path("accounts/logout/", logout_view, name="logout"),
    path("accounts/", include("allauth.urls")),
    # Local apps
    path("", include("main.urls")),
    # Third-party apps
    path("__debug__/", include("debug_toolbar.urls")),
]
