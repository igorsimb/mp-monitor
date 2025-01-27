from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from api.v1 import views

router = DefaultRouter()
router.register("items", views.ItemViewSet)
router.register("orders", views.OrderViewSet)
router.register("tenants", views.TenantViewSet)
router.register("users", views.UserViewSet)
router.register("quotas", views.TenantQuotaViewSet)
router.register("plans", views.PaymentPlanViewSet)

urlpatterns = [
    path("", include(router.urls)),
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
