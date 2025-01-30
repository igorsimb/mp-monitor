import uuid

from rest_framework import serializers

from accounts.models import Tenant, PaymentPlan, TenantQuota, User
from main.models import Item, Order


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "tenant", "name", "sku", "price", "is_in_stock"]


class OrderSerializer(serializers.ModelSerializer):
    order_id = serializers.UUIDField(read_only=True, default=uuid.uuid4)

    class Meta:
        model = Order
        fields = ["tenant", "order_id", "amount", "description", "order_intent", "created_at", "status"]
        extra_kwargs = {"tenant": {"read_only": True}}


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["name", "payment_plan", "balance", "quota"]


class TenantQuotaSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.get_name_display()

    class Meta:
        model = TenantQuota
        fields = ["name", "skus_limit", "parse_units_limit"]


class PaymentPlanSerializer(serializers.ModelSerializer):
    quotas = TenantQuotaSerializer()
    name = serializers.SerializerMethodField()

    def get_name(self, obj):
        return obj.get_name_display()

    class Meta:
        model = PaymentPlan
        fields = ["name", "price", "quotas"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["tenant", "created_at", "is_demo_user"]
