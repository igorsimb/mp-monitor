from django.urls import path, include
from rest_framework.routers import DefaultRouter

from api import views

router = DefaultRouter()
router.register("items", views.ItemViewSet)
router.register("orders", views.OrderViewSet)
router.register("tenants", views.TenantViewSet)
router.register("quotas", views.TenantQuotaViewSet)
router.register("plans", views.PaymentPlanViewSet)

urlpatterns = [
    path("", include(router.urls)),
]
