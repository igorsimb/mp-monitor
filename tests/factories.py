import factory
from django_celery_beat.models import PeriodicTask, IntervalSchedule
from factory.django import DjangoModelFactory

from accounts.models import Tenant, TenantQuota, PaymentPlan, Profile
from config import DEFAULT_QUOTAS, PlanType
from main.models import Item
from mp_monitor import settings
from notifier.models import PriceAlert


class TenantFactory(DjangoModelFactory):
    class Meta:
        model = Tenant

    name = factory.Sequence(lambda n: f"test_tenant_{n + 1}@testing.com")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = settings.AUTH_USER_MODEL

    # Sequence preferred over factory.Faker("email") to better match username using similar sequence
    email = factory.Sequence(lambda n: f"user_{n}@testing.com")
    username = factory.Sequence(lambda n: f"user_{n}")
    password = factory.PostGenerationMethodCall("set_password", "password")
    tenant = factory.RelatedFactory(TenantFactory)


# currently not used since signal auto-creates profile when creating user
# if you need to test profile creation separately, disable signals in the test
class ProfileFactory(DjangoModelFactory):
    class Meta:
        model = Profile

    user = factory.SubFactory(UserFactory)
    display_name = factory.Faker("name")
    info = factory.Faker("paragraph")


class IntervalScheduleFactory(DjangoModelFactory):
    class Meta:
        model = IntervalSchedule

    every = 10
    period = IntervalSchedule.SECONDS


class PeriodicTaskFactory(DjangoModelFactory):
    class Meta:
        model = PeriodicTask

    name = "test_periodic_task"
    task = "test_task"
    interval = factory.SubFactory(IntervalScheduleFactory)
    args = ["test_arg_1", "test_arg_2"]


class ItemFactory(DjangoModelFactory):
    class Meta:
        model = Item

    tenant = factory.SubFactory(TenantFactory, name=UserFactory.email)
    name = factory.Sequence(lambda n: f"item_{n + 1}")
    sku = factory.Sequence(lambda n: f"{n + 1}" * 5)
    price = factory.Sequence(lambda n: (n + 1) * 100)


class TenantQuotaFactory(DjangoModelFactory):
    class Meta:
        model = TenantQuota

    name = factory.Sequence(lambda n: f"test_quota_{n + 1}")
    total_hours_allowed = DEFAULT_QUOTAS[PlanType.FREE.value]["total_hours_allowed"]
    skus_limit = DEFAULT_QUOTAS[PlanType.FREE.value]["skus_limit"]
    parse_units_limit = DEFAULT_QUOTAS[PlanType.FREE.value]["parse_units_limit"]


class PaymentPlanFactory(DjangoModelFactory):
    class Meta:
        model = PaymentPlan

    name = PaymentPlan.PlanName.BUSINESS.value
    price = 6000


class PriceAlertFactory(DjangoModelFactory):
    class Meta:
        model = PriceAlert

    tenant = factory.SubFactory(TenantFactory)
    items = factory.RelatedFactory(ItemFactory, "price_alerts")
    target_price = factory.Faker("random_int", min=0, max=100)
    target_price_direction = PriceAlert.TargetPriceDirection.UP
    message = factory.Faker("sentence")
    is_active = True
