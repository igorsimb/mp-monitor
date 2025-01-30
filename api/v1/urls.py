from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
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
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("schema/swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("schema/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("tenants/plan-info/", views.TenantPlanAPIView.as_view()),
    path("", include(router.urls)),
]
