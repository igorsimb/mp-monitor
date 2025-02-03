from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import viewsets, generics
from rest_framework.permissions import IsAuthenticated, IsAdminUser

from accounts.models import Tenant, PaymentPlan, TenantQuota, User
from api.v1.filters import ItemFilter, OrderFilter
from api.v1.serializers import (
    ItemSerializer,
    OrderSerializer,
    TenantSerializer,
    PaymentPlanSerializer,
    TenantQuotaSerializer,
    UserSerializer,
    TenantPlanSerializer,
)
from main.models import Item, Order


class ItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Item.objects.all()
    serializer_class = ItemSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = ItemFilter
    filter_backends = [DjangoFilterBackend]

    # uncomment method decorators when redis is running
    # @method_decorator(cache_page(60 * 15, key_prefix="item_list"))
    # @method_decorator(vary_on_headers("Authorization"))
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        """
        Admins can see all items, but non-admins can only see their own items
        """
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(tenant=self.request.user.tenant)
        return qs


class OrderViewSet(viewsets.ModelViewSet):
    queryset = Order.objects.all()
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    filterset_class = OrderFilter
    filter_backends = [DjangoFilterBackend]

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(tenant=self.request.user.tenant)
        return qs

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.tenant)


class TenantViewSet(viewsets.ModelViewSet):
    queryset = Tenant.objects.all()
    serializer_class = TenantSerializer
    permission_classes = [IsAdminUser]


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]


class TenantQuotaViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = TenantQuota.objects.all()
    serializer_class = TenantQuotaSerializer
    permission_classes = [IsAuthenticated]


class PaymentPlanViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = PaymentPlan.objects.all()
    serializer_class = PaymentPlanSerializer
    permission_classes = [IsAuthenticated]


class TenantPlanAPIView(generics.ListAPIView):
    """
    List of all Tenants with their Payment Plans
    """

    queryset = Tenant.objects.select_related("payment_plan")
    serializer_class = TenantPlanSerializer
    permission_classes = [IsAdminUser]
