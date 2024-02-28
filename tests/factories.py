import factory
from factory.django import DjangoModelFactory

from main.models import Tenant
from mp_monitor import settings


class TenantFactory(DjangoModelFactory):
    class Meta:
        model = Tenant


class UserFactory(DjangoModelFactory):
    class Meta:
        model = settings.AUTH_USER_MODEL

    # Sequence preferred over factory.Faker("email") to better match username using similar sequence
    email = factory.Sequence(lambda n: f"user_{n}@testing.com")
    username = factory.Sequence(lambda n: f"user_{n}")
    password = factory.PostGenerationMethodCall("set_password", "password")
    tenant = factory.RelatedFactory(TenantFactory, "name")
