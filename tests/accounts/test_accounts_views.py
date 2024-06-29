import logging

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

import config
from accounts.models import TenantQuota
from main.models import Item
from tests.factories import UserFactory, PeriodicTaskFactory

logger = logging.getLogger(__name__)

User = get_user_model()
client = Client()


class TestLogoutView:
    def test_redirect_to_main_page(self, client):
        user = UserFactory()
        client.login(username=user.username, password=user.password)
        assert user.is_authenticated
        response = client.get(reverse("logout"), follow=True)
        assert response.status_code == 200
        assert "Главная" in response.content.decode()  # content is a bytes-like object, hence decode()

    def test_user_is_logged_out(self, client):
        """
        Check if the user is logged out after logging out by directly accessing the user
        associated with the request object in the response (response.wsgi_request.user),
        """
        user = UserFactory()
        client.force_login(user)
        response = client.get(reverse("logout"))
        assert not response.wsgi_request.user.is_authenticated

    def test_logout_user_with_next_url(self, client):
        """
        Check if user is logged out and redirected to the next URL after logging out.
        """
        user = UserFactory()
        client.force_login(user)
        next_url = reverse("account_signup")

        response = client.get(reverse("logout") + f"?next={next_url}")

        assert not response.wsgi_request.user.is_authenticated
        assert response.url == next_url


@pytest.mark.demo_user
class TestDemoView:
    def test_redirect_to_correct_template(self, client):
        template_name = "main/item_list.html"
        response = client.get(reverse("demo"), follow=True)
        assert response.status_code == 200
        assert template_name in response.template_name

    def test_demo_user_is_created(self, client):
        client.get(reverse("demo"))
        user = User.objects.get(username__startswith="demo-user")
        assert user.is_demo_user
        assert user.is_demo_active

    def test_demo_user_is_authenticated(self, client):
        client.get(reverse("demo"))
        user = User.objects.get(username__startswith="demo-user")
        assert user.is_authenticated

    def test_demo_user_quota(self, client):
        """
        Checks if the demo user has the correct quota.
        """
        client.get(reverse("demo"))
        user = User.objects.get(username__startswith="demo-user")
        user_quota = TenantQuota.objects.get(user=user)
        items = Item.objects.filter(tenant=user.tenant)
        assert user_quota.user_lifetime_hours == config.DEMO_USER_EXPIRATION_HOURS
        assert user_quota.max_allowed_skus == config.DEMO_USER_MAX_ALLOWED_SKUS - len(items)
        assert user_quota.manual_updates == config.DEMO_USER_MANUAL_UPDATES
        assert user_quota.scheduled_updates == config.DEMO_USER_SCHEDULED_UPDATES


@pytest.mark.demo_user
class TestCheckExpiredDemoUsers:
    @pytest.fixture
    def create_active_demo_user(self) -> User:
        demo_user = UserFactory(
            is_demo_user=True,
            is_demo_active=True,
        )
        return demo_user

    @pytest.fixture
    def create_expired_demo_user(self) -> User:
        """
        Demo user created in the past beyond the DEMO_USER_EXPIRATION_HOURS threshold.
        """
        demo_user = UserFactory(
            is_demo_user=True,
            is_demo_active=True,
        )
        demo_user.created_at = timezone.now() - timezone.timedelta(hours=config.DEMO_USER_EXPIRATION_HOURS + 1)
        demo_user.save()
        return demo_user

    def test_expired_demo_user_properties(self, create_expired_demo_user: User) -> None:
        """
        Check that expired demo user properties are correct.
        """
        demo_user = create_expired_demo_user
        assert demo_user.is_demo_expired
        assert not demo_user.is_active_demo_user

    def test_expired_demo_user_is_deactivated(self, client: Client, create_expired_demo_user: User) -> None:
        """
        Check that expired demo user is deactivated. Can only be done by superuser.
        """
        superuser = UserFactory(username="superuser")
        superuser.is_superuser = True
        superuser.save()
        demo_user = create_expired_demo_user

        logger.info("Checking that expired demo user is active...")
        assert demo_user.is_active

        client.force_login(superuser)
        logger.info("Deactivating expired demo user...")
        client.post(reverse("check_expired_demo_users"))

        logger.debug("Refreshing demo user from database...")
        demo_user.refresh_from_db()
        logger.info("Checking that expired demo user has ben deactivated...")
        assert not demo_user.is_active
        assert not demo_user.is_demo_active

    def test_periodic_task_is_deleted_for_expired_demo_user(
        self, client: Client, create_expired_demo_user: User
    ) -> None:
        superuser = UserFactory(username="superuser")
        superuser.is_superuser = True
        superuser.save()
        demo_user = create_expired_demo_user
        logger.info("Creating periodic task for demo user...")
        PeriodicTaskFactory(name=f"task_tenant_{demo_user.tenant.id}")

        client.force_login(superuser)
        logger.info("Checking periodic task was created...")
        assert PeriodicTask.objects.count() == 1

        client.post(reverse("check_expired_demo_users"))
        logger.info("Checking periodic task was deleted after demo user was deactivated...")
        assert (
            PeriodicTask.objects.count() == 0
        ), f"Demo user should have 0 periodic tasks, but has {PeriodicTask.objects.count()}"

    def test_no_modification_made_to_active_demo_user(self, client: Client, create_active_demo_user: User) -> None:
        superuser = UserFactory(username="superuser")
        superuser.is_superuser = True
        superuser.save()
        demo_user = create_active_demo_user
        logger.info("Creating periodic task for demo user...")
        PeriodicTaskFactory(name=f"task_tenant_{demo_user.tenant.id}")

        client.force_login(superuser)
        logger.info("Checking periodic task was created...")
        assert PeriodicTask.objects.count() == 1

        client.post(reverse("check_expired_demo_users"))

        assert demo_user.is_active
        assert demo_user.is_demo_active
        logger.info("Checking periodic task was not deleted for active demo user...")
        assert (
            PeriodicTask.objects.count() == 1
        ), f"Demo user should have 0 periodic tasks, but has {PeriodicTask.objects.count()}"
