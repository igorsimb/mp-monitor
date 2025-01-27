from rest_framework import viewsets

from accounts.models import Tenant, PaymentPlan, TenantQuota
from api.serializers import (
    ItemSerializer,
    OrderSerializer,
    TenantSerializer,
    PaymentPlanSerializer,
    TenantQuotaSerializer,
)
from main.models import Item, Order


class ItemViewSet(viewsets.ModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer


class TenantQuotaViewSet(viewsets.ModelViewSet):
    queryset = TenantQuota.objects.all()
    serializer_class = TenantQuotaSerializer


class PaymentPlanViewSet(viewsets.ModelViewSet):
    queryset = PaymentPlan.objects.all()
    serializer_class = PaymentPlanSerializer
