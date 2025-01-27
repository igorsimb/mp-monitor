from rest_framework import serializers

from accounts.models import Tenant, PaymentPlan, TenantQuota
from main.models import Item, Order


class ItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = Item
        fields = ["id", "tenant", "name", "sku", "price", "is_in_stock"]


class OrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = ["id", "tenant", "order_id", "amount", "description", "order_intent", "created_at", "status"]


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = ["id", "name", "payment_plan", "balance", "quota"]


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
