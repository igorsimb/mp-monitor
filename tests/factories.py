import factory
from factory.django import DjangoModelFactory

from accounts.models import CustomUser
from main.models import Tenant


class TenantFactory(DjangoModelFactory):
    class Meta:
        model = Tenant


class UserFactory(DjangoModelFactory):
    class Meta:
        model = CustomUser

    email = factory.Faker("email")
