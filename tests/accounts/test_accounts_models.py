import logging
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.dispatch import Signal

from accounts.models import PaymentPlan
from accounts.models import Tenant, Profile
from accounts.signals import add_user_to_group
from config import DEFAULT_QUOTAS, PlanType
from tests.factories import UserFactory, TenantQuotaFactory, TenantFactory

logger = logging.getLogger(__name__)

User = get_user_model()


class TestUserModel:
    def test_user_exists(self) -> None:
        user = UserFactory()

        assert user is not None

    def test_custom_user_creation(self):
        user = User.objects.create(email="testuser@test.com", username="testuser", password="testpassword")

        assert user.email == "testuser@test.com"
        assert user.password == "testpassword"
        assert user.username == "testuser"

    @pytest.mark.demo_user
    def test_demo_user_creation(self):
        user = UserFactory(is_demo_user=True)
        assert user.is_demo_user is True

    def test_tenant_is_created_automatically_from_email(self):
        user = User.objects.create(email="testuser2@test.com", username="testuser2", password="testpassword")
        logger.info("user.tenant.name = %s", user.tenant.name)
        assert user.tenant.name == f"testuser2@test.com_{Tenant.objects.count()}", f"{user.tenant.name=}"

    def test_user_creation_with_existing_tenant(self):
        existing_tenant = Tenant.objects.create(name="existing_tenant")
        user = User.objects.create(username="testuser3", password="testpassword", tenant=existing_tenant)
        assert user.tenant == existing_tenant


class TestTenantModel:
    def test_tenant_creation(self):
        tenant = TenantFactory()
        assert tenant is not None

    def test_switch_plan(self):
        tenant = TenantFactory()
        plan = PaymentPlan.objects.create(name="2")
        plan.save()
        logger.debug("Tenant Old Plan: %s (%s)" % (tenant.payment_plan.name, type(tenant.payment_plan.name)))
        plan.refresh_from_db()
        tenant.switch_plan(new_plan="2")
        tenant.save()
        tenant.refresh_from_db()
        logger.debug("Tenant New Plan: %s" % tenant.payment_plan.name)
        assert tenant.quota.name == PaymentPlan.PlanName.BUSINESS

    def test_tenant_new_plan_quota_is_correct(self):
        tenant = TenantFactory()
        old_plan = tenant.payment_plan
        new_plan = PaymentPlan.objects.create(name="2")
        tenant.switch_plan(new_plan="2")

        assert old_plan != new_plan
        assert tenant.quota.skus_limit == DEFAULT_QUOTAS[PlanType.BUSINESS.value]["skus_limit"]
        assert tenant.quota.parse_units_limit == DEFAULT_QUOTAS[PlanType.BUSINESS.value]["parse_units_limit"]

    def test_add_to_balance(self):
        """
        Check if the balance is updated correctly when a new payment is made.
        """
        tenant = TenantFactory()
        tenant.add_to_balance(Decimal("10.00"))
        assert tenant.balance == Decimal("10.00")

    def test_add_negative_to_balance(self):
        """
        Check ValueError is raised when trying to add a negative amount to the balance.
        """
        tenant = TenantFactory()
        with pytest.raises(ValueError):
            tenant.add_to_balance(Decimal("-10.00"))

    def test_deduct_from_balance(self):
        """
        Check if the balance is updated correctly when deducting an amount from the balance.
        """
        tenant = TenantFactory()
        tenant.balance = Decimal("15.00")
        tenant.deduct_from_balance(Decimal("10.00"))
        assert tenant.balance == Decimal("5.00")

    def test_deduct_negative_from_balance(self):
        """
        Check ValueError is raised when trying to deduct a negative amount from the balance.
        """
        tenant = TenantFactory()
        tenant.balance = Decimal("10.00")
        with pytest.raises(ValueError):
            tenant.deduct_from_balance(Decimal("-10.00"))

    def test_deduct_more_than_balance(self):
        """
        Check ValueError is raised when trying to deduct more than the balance.
        """
        tenant = TenantFactory()
        tenant.balance = Decimal("10.00")
        with pytest.raises(ValueError):
            tenant.deduct_from_balance(Decimal("20.00"))


@pytest.fixture
def setup_signal_test():
    tenant = Tenant.objects.create(name="test_tenant")
    user = User.objects.create(email="testuser@test.com", username="testuser", tenant=tenant)

    logger.debug("Creating a signal to connect the function to post_save")
    signal = Signal()
    signal.connect(add_user_to_group, sender=User, dispatch_uid="test_signal")

    return user, signal


# pylint: disable=redefined-outer-name
class TestAddUserToGroup:
    def test_group_created(self, setup_signal_test):
        user, signal = setup_signal_test

        logger.debug("Emitting signal with created=True")
        signal.send(sender=User, instance=user, created=True)

        logger.info("Checking if the user is added to group '%s'", user.tenant.name)
        group = Group.objects.get(name=user.tenant.name)
        assert group in user.groups.all()

    def test_remove_tenant_from_user(self, setup_signal_test):
        user, signal = setup_signal_test

        logger.info("Removing tenant from user...")
        user.tenant = None
        logger.info("Tenant removed from user, user.tenant = %s", user.tenant)
        user.save()
        logger.info("Saved user, user.tenant = %s", user.tenant)

        logger.debug("Emitting signal with created=True")
        signal.send(sender=User, instance=user, created=True)

        logger.info("Checking if the user is added to a group after saving the user...")
        assert user.groups.count() == 1

    def test_tenant_name_change_causes_group_change(self, setup_signal_test):
        user, signal = setup_signal_test

        logger.debug("Emitting signal with created=True")
        signal.send(sender=User, instance=user, created=True)

        old_group = Group.objects.filter(name=user.tenant.name).first()

        logger.info("Changing current tenant name (%s)", user.tenant.name)
        user.tenant.name = "new_tenant_name"
        user.tenant.save()
        logger.info("New tenant name is %s", user.tenant.name)

        logger.debug("Emitting post-save signal again")
        signal.send(sender=User, instance=user, created=False)

        logger.info("Checking if the user is removed from the old group and added to the new group")
        new_group = Group.objects.filter(name="new_tenant_name").first()
        logger.info("New group: %s", new_group)
        assert old_group not in user.groups.all()
        assert new_group in user.groups.all()


class TestUserQuotaModel:
    def test_tenant_quota_creation(self):
        tenant = TenantFactory()
        tenant.quota = TenantQuotaFactory(name="test_quota")
        assert tenant.quota is not None
        assert tenant.quota.name == "test_quota"

    def test_tenant_quota_update(self):
        tenant = TenantFactory()
        tenant.quota = TenantQuotaFactory(name="test_quota")
        old_limit = tenant.quota.parse_units_limit
        assert tenant.quota.parse_units_limit == old_limit

        new_limit = tenant.quota.parse_units_limit = 150
        assert tenant.quota.parse_units_limit == new_limit
        assert old_limit != new_limit


class TestProfileModel:
    @pytest.fixture
    def profile(self):
        """
        Profile with the related user and blank fields otherwise
        """
        user = UserFactory()
        profile = Profile.objects.get(user=user)
        return profile

    def test_profile_is_created(self, profile):
        """
        Check that profile is created when user is created
        """
        assert profile is not None

    def test_profile_user(self):
        user = UserFactory(email="test_email@test.com", username="test_username")
        profile = Profile.objects.get(user=user)
        assert profile.user.email == "test_email@test.com"
        assert profile.user.username == "test_username"

    def test_change_display_name(self, profile):
        assert profile.display_name is None
        profile.display_name = "new_name"
        assert profile.display_name == "new_name"

    def test_change_info(self, profile):
        assert profile.info is None
        profile.info = "new info"
        assert profile.info == "new info"

    def test_profile_default_name(self, profile):
        """
        Checks that `name` property defaults to user's username if no display_name is provided
        """
        assert profile.name == profile.user.username

    def test_profile_name_filled(self, profile):
        """
        Checks that `name` property if display_name is provided
        """
        new_name = "new display name"
        profile.display_name = new_name
        assert profile.name == new_name
