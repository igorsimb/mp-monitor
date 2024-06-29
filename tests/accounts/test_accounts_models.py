import logging

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.dispatch import Signal

from accounts.models import User, add_user_to_group
from accounts.models import Tenant
from tests.factories import UserFactory, UserQuotaFactory

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
        assert user.tenant.name == "testuser2@test.com", f"{user.tenant.name=}"

    def test_user_creation_with_existing_tenant(self):
        existing_tenant = Tenant.objects.create(name="existing_tenant")
        user = User.objects.create(username="testuser3", password="testpassword", tenant=existing_tenant)
        assert user.tenant == existing_tenant


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
    def test_user_quota_creation(self):
        user = UserFactory()
        quota = UserQuotaFactory(user=user)
        assert quota.user == user

    def test_user_quota_update(self):
        user = UserFactory()
        quota = UserQuotaFactory(user=user)
        quota.user_lifetime_hours = 10
        quota.save()
        assert quota.user_lifetime_hours == 10
