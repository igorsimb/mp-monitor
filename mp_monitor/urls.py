from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # Django admin
    path('admin/', admin.site.urls),

    # User management
    path('accounts/', include('allauth.urls')),

    # Local apps
    path('', include('main.urls')),

    # Third-party apps
    path('__debug__/', include('debug_toolbar.urls')),
]
