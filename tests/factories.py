import factory
from factory.django import DjangoModelFactory

from main.models import Tenant
from mp_monitor import settings


class TenantFactory(DjangoModelFactory):
    class Meta:
        model = Tenant

    name = factory.Faker("email")


class UserFactory(DjangoModelFactory):
    class Meta:
        model = settings.AUTH_USER_MODEL

    username = factory.Faker("user_name")
    email = factory.Faker("email")
    password = factory.PostGenerationMethodCall("set_password", "password")
