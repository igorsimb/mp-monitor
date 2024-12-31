import logging

import pytest
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

import config
from accounts.forms import EmailChangeForm
from main.models import Item
from tests.factories import UserFactory, PeriodicTaskFactory

logger = logging.getLogger(__name__)

User = get_user_model()


class TestLogoutView:
    @pytest.fixture(scope="class")
    def client(self):
        self.client = Client()
        return self.client

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
    @pytest.fixture(scope="class")
    def client(self):
        self.client = Client()
        return self.client

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
        items = Item.objects.filter(tenant=user.tenant)
        assert user.tenant.quota.total_hours_allowed == config.DEMO_USER_HOURS_ALLOWED
        assert user.tenant.quota.skus_limit == config.DEMO_USER_MAX_ALLOWED_SKUS - len(items)


@pytest.mark.demo_user
class TestCheckExpiredDemoUsers:
    @pytest.fixture(scope="class")
    def client(self):
        self.client = Client()
        return self.client

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
        Demo user created in the past beyond the DEMO_USER_HOURS_ALLOWED threshold.
        """
        demo_user = UserFactory(
            is_demo_user=True,
            is_demo_active=True,
        )
        demo_user.created_at = timezone.now() - timezone.timedelta(hours=config.DEMO_USER_HOURS_ALLOWED + 1)
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


class TestProfileViews:
    @pytest.fixture
    def client(self) -> Client:
        self.client = Client()
        return self.client

    @pytest.fixture
    def logged_in_user(self, client: Client) -> User:
        user = UserFactory()
        user.set_password("testpassword")
        user.save()
        client.login(username=user.username, password="testpassword")  # Use the correct password
        return user

    def test_profile_view(self, client: Client, logged_in_user: User) -> None:
        response = client.get(reverse("profile"), follow=True)
        assert response.status_code == 200

    def test_profile_edit_view(self, client: Client, logged_in_user: User) -> None:
        response = client.get(reverse("profile_edit"), follow=True)
        assert response.context["onboarding"] is False
        assert response.status_code == 200

    def test_profile_edit_with_onboarding(self, client: Client, logged_in_user: User) -> None:
        response = client.get(reverse("profile_onboarding"), follow=True)
        assert response.context["onboarding"] is True
        assert response.status_code == 200

    def test_profile_settings_view(self, client: Client, logged_in_user: User) -> None:
        response = client.get(reverse("profile_settings"), follow=True)
        assert response.status_code == 200

    def test_email_verify_redirect(self, client: Client, logged_in_user: User) -> None:
        response = client.get(reverse("email_verify"))
        assert response.status_code == 302
        assert response.url == reverse("profile_settings")

    def test_profile_delete_view_get(self, client: Client, logged_in_user: User) -> None:
        response = client.get(reverse("profile_delete"))
        assert response.status_code == 200
        assert "account/profile_delete.html" in [t.name for t in response.templates]

    def test_profile_delete_view_user_redirected(self, client: Client, logged_in_user: User) -> None:
        response = client.post(reverse("profile_delete"))
        assert response.status_code == 302

    def test_profile_delete_view_redirect_url(self, client: Client, logged_in_user: User) -> None:
        response = client.post(reverse("profile_delete"))
        assert response.url == reverse("index")

    def test_profile_delete_view_user_deleted(self, client: Client, logged_in_user: User) -> None:
        client.post(reverse("profile_delete"))
        assert not User.objects.filter(id=logged_in_user.id).exists()

    def test_profile_delete_view_message_called(self, client: Client, logged_in_user: User) -> None:
        response = client.post(reverse("profile_delete"))
        messages_list = list(messages.get_messages(response.wsgi_request))
        assert len(messages_list) == 1

    def test_profile_delete_view_unauthenticated_get(self, client: Client) -> None:
        response = client.get(reverse("profile_delete"))
        assert response.status_code == 302
        assert reverse("account_login") in response.url

    def test_profile_delete_view_unauthenticated_post(self, client: Client) -> None:
        response = client.post(reverse("profile_delete"))
        assert response.status_code == 302
        assert reverse("account_login") in response.url


class TestEmailChangeView:
    @pytest.fixture(scope="class")
    def client(self) -> Client:
        self.client = Client()
        return self.client

    @pytest.fixture
    def logged_in_user(self, client: Client) -> User:
        user = UserFactory()
        user.set_password("testpassword")
        user.save()
        client.login(username=user.username, password="testpassword")  # Use the correct password
        return user

    def test_form_is_instance_of_EmailChangeForm(self, client: Client, logged_in_user: User) -> None:
        response_htmx = client.get(reverse("email_change"), HTTP_HX_REQUEST="true", follow=True)
        assert response_htmx.status_code == 200
        assert isinstance(response_htmx.context["form"], EmailChangeForm)

    def test_non_htmx_redirect(self, client: Client, logged_in_user: User) -> None:
        response = client.get(reverse("email_change"), follow=True)
        current_url = response.request["PATH_INFO"]
        print(f"Current URL: {current_url}")
        assert current_url == reverse("item_list")

    def test_post_with_valid_email(self, client: Client, logged_in_user: User) -> None:
        new_email = "new_email@example.com"
        response = client.post(reverse("email_change"), data={"email": new_email})

        logger.info("Checking if email was updated...")
        logged_in_user.refresh_from_db()
        assert logged_in_user.email == new_email

        logger.info("Checking redirection...")
        assert response.status_code == 302
        assert response.url == reverse("profile_settings")

    def test_post_with_existing_email(self, client: Client, logged_in_user: User) -> None:
        existing_user = UserFactory(email="existing_email@example.com")

        response = client.post(reverse("email_change"), data={"email": existing_user.email})

        logger.info("Checking if redirected to profile settings...")
        assert response.status_code == 302
        assert response.url == reverse("profile_settings")

        msg = list(messages.get_messages(response.wsgi_request))
        logger.info("Checking if messages have occurred: %s", msg)

        # Check for warning message in session messages
        assert list(messages.get_messages(response.wsgi_request))

    def test_post_with_invalid_data(self, client: Client, logged_in_user: User) -> None:
        response = client.post(reverse("email_change"), data={"email": "invalid-email"})

        logger.info("Checking if redirected to profile settings...")
        assert response.status_code == 302
        assert response.url == reverse("profile_settings")

        msg = list(messages.get_messages(response.wsgi_request))
        logger.info("Checking if messages have occurred: %s", msg)

        assert list(messages.get_messages(response.wsgi_request))
