from accounts.models import TenantQuota, PaymentPlan
from config import PlanType, DEFAULT_QUOTAS
from tests.factories import TenantFactory


def test_default_plan_is_assigned() -> None:
    """Test that the default payment plan is assigned to a new tenant."""
    tenant = TenantFactory()
    free_plan = PaymentPlan.get_default_payment_plan()
    assert tenant.payment_plan == free_plan


def test_default_plan_is_free() -> None:
    """Test that the default payment plan is FREE."""
    tenant = TenantFactory()
    assert tenant.payment_plan.name == PaymentPlan.PlanName.FREE.value


def test_default_plan_quota_is_assigned() -> None:
    """Test that the default quota is assigned to a new tenant."""
    tenant = TenantFactory()
    free_plan_quota = TenantQuota.get_default_quota()
    assert tenant.quota == free_plan_quota


def test_default_plan_quota_is_correct() -> None:
    """Test that the default quota is the same as in config.py file."""
    tenant = TenantFactory()
    assert tenant.quota.skus_limit == DEFAULT_QUOTAS[PlanType.FREE.value]["skus_limit"]
    assert tenant.quota.parse_units_limit == DEFAULT_QUOTAS[PlanType.FREE.value]["parse_units_limit"]


def test_not_default_plan_quota_is_not_correct() -> None:
    """Test that the default quota is not BUSINESS plan quota from config.py file."""
    tenant = TenantFactory()
    assert tenant.quota.skus_limit != DEFAULT_QUOTAS[PlanType.BUSINESS.value]["skus_limit"]
    assert tenant.quota.parse_units_limit != DEFAULT_QUOTAS[PlanType.BUSINESS.value]["parse_units_limit"]
