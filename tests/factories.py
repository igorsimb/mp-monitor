import factory
from factory.django import DjangoModelFactory
from django_celery_beat.models import PeriodicTask, IntervalSchedule

from main.models import Item
from accounts.models import Tenant, TenantQuota
from mp_monitor import settings


class TenantFactory(DjangoModelFactory):
    class Meta:
        model = Tenant

    name = factory.Sequence(lambda n: f"test_tenant_{n+1}@testing.com")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = settings.AUTH_USER_MODEL

    # Sequence preferred over factory.Faker("email") to better match username using similar sequence
    email = factory.Sequence(lambda n: f"user_{n}@testing.com")
    username = factory.Sequence(lambda n: f"user_{n}")
    password = factory.PostGenerationMethodCall("set_password", "password")
    tenant = factory.RelatedFactory(TenantFactory)


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
    name = factory.Sequence(lambda n: f"item_{n+1}")
    sku = factory.Sequence(lambda n: f"{n+1}" * 5)


class TenantQuotaFactory(DjangoModelFactory):
    class Meta:
        model = TenantQuota

    name = factory.Sequence(lambda n: f"test_quota_{n+1}")
    total_hours_allowed = 10
    skus_limit = 10
    parse_units_limit = 100
