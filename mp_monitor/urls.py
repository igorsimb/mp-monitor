from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from accounts.views import logout_view, demo_view, check_expired_demo_users

urlpatterns = [
    # Django admin
    path("definitely-not-admin/", admin.site.urls),
    # User management
    path("accounts/logout/", logout_view, name="logout"),
    path("profile/", include("accounts.urls")),
    path("demo/", demo_view, name="demo"),
    path("accounts/", include("allauth.urls")),
    # path("demo-expired/<int:pk>/", check_expired_demo, name="check_expired_demo"),
    path("demo-expired/", check_expired_demo_users, name="check_expired_demo_users"),
    # path("demo-error/", demo_error_view, name="demo_error_page"),
    # Local apps
    path("", include("main.urls")),
    path("notifier/", include("notifier.urls")),
    path("api/v1/", include("api.v1.urls")),
    # Third-party apps
    path("__debug__/", include("debug_toolbar.urls")),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
