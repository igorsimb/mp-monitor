import logging
from datetime import datetime
from typing import Type, Any

import httpx
import pytest
import pytz
from django.contrib.auth import get_user_model
from django.core.handlers.wsgi import WSGIRequest
from django.http import Http404
from django.test import RequestFactory, Client
from django.urls import reverse
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from accounts.models import TenantQuota
from factories import IntervalScheduleFactory, PeriodicTaskFactory, UserFactory
from main.forms import ScrapeForm, ScrapeIntervalForm
from main.models import Item
from main.utils import task_name
from main.views import (
    ItemListView,
    ItemDetailView,
    scrape_items,
    destroy_scrape_interval_task,
    update_items,
    update_scrape_interval,
)
from tests.factories import TenantQuotaFactory

logger = logging.getLogger(__name__)

User = get_user_model()
client = Client()


class TestIndex:
    def test_unauthenticated(self, client: Client) -> None:
        """An unauthenticated user gets a valid response"""
        response = client.get(reverse("index"))

        assert response.status_code == 200

    def test_authenticated_user_is_redirected(self, client: Client) -> None:
        """An authenticated user is redirected to a correct destination"""
        user = UserFactory()
        client.force_login(user)

        logger.info("Checking that authenticated user gets redirected...")
        response = client.get(reverse("index"))
        assert response.status_code == 302

        redirect_url_name = "item_list"
        destination = client.get(reverse(redirect_url_name))
        logger.info("Checking that authenticated user is redirected to '%s' url...", redirect_url_name)
        assert destination.status_code == 200


class TestItemListView:
    context_object_list = [
        "items",
        "sku",
        "form",
        "scrape_interval_form",
    ]

    @pytest.fixture
    def request_with_user(self) -> WSGIRequest:
        """Returns a WSGIRequest object with a logged-in user and an empty session.

        This fixture can be used to test views that require authentication
        """
        url = reverse("item_list")
        factory = RequestFactory()
        user = User.objects.create_user(username="testuser", email="testuser@test.com", password="testpassword")
        request = factory.get(url)
        request.user = user
        request.session = {}

        return request

    # https://docs.djangoproject.com/en/4.2/topics/testing/advanced/#testing-class-based-views
    @pytest.mark.parametrize("expected_context_item", context_object_list)
    def test_non_existing_task_not_present_in_context(
        self, request_with_user: WSGIRequest, expected_context_item: str
    ) -> None:
        request = request_with_user

        view = ItemListView()
        view.setup(request)

        logger.info(
            "Initializing 'object_list' attribute for '%s' view",
            view.__class__.__name__,
        )
        view.object_list = view.get_queryset()
        logger.debug("view.object_list = %s", view.object_list)

        context = view.get_context_data()
        assert expected_context_item in context

    def test_existing_task_present_in_context(self, request_with_user: WSGIRequest) -> None:
        user = request_with_user.user
        expected_context_items = ["scrape_interval_task", "next_interval_run_at"]

        PeriodicTaskFactory(
            name=task_name(user),
            interval=IntervalScheduleFactory(every=10, period="minutes"),
            args=["arg1", 1],
            last_run_at=timezone.now(),
        )

        request = request_with_user
        view = ItemListView()
        view.setup(request)

        logger.info(
            "Initializing 'object_list' attribute for '%s' view to access its get_context_data()",
            view.__class__.__name__,
        )
        view.object_list = view.get_queryset()
        logger.debug("view.object_list = %s", view.object_list)

        context = view.get_context_data()
        for item in expected_context_items:
            logger.info("Checking that '%s' is in context", item)
            assert item in context

    def test_next_interval_run_is_calculated_correctly_in_context(self, request_with_user: WSGIRequest) -> None:
        """
        Tests that the `next_interval_run_at` value in the view context is calculated correctly for periodic tasks
        with a previously run time (`last_run_at` not None).

        This test simulates a scenario where a view (`ItemListView` in this case) has a periodic task associated with it.
        It verifies that the calculated `next_interval_run_at` based on the task's schedule (`run_every` and `period`)
        matches the corresponding value stored in the view's context data.

        **Key points:**

        - The test creates a sample periodic task with a schedule and sets its `last_run_at` to the current time.
        - It retrieves the context data from the view after setting up the object list.
        - Both the calculated `next_interval_run_at` and the one from the context are converted to UTC and adjusted
          to remove seconds and microseconds for tolerance in the assertion (1-minute tolerance).
        - Finally, the test asserts that the two `next_interval_run_at` values are equal.
        """
        user = request_with_user.user

        task = PeriodicTaskFactory(
            name=task_name(user),
            interval=IntervalScheduleFactory(every=10, period="minutes"),
            args=["arg1", 1],
            last_run_at=timezone.now(),
        )

        task.last_run_at = datetime.now()
        request = request_with_user
        view = ItemListView()
        view.setup(request)

        logger.info(
            "Initializing 'object_list' attribute for '%s' view to access its get_context_data()",
            view.__class__.__name__,
        )
        view.object_list = view.get_queryset()
        logger.debug("view.object_list = %s", view.object_list)

        context = view.get_context_data()

        next_interval_run_at = task.last_run_at + task.schedule.run_every
        logger.info("Removing seconds and microseconds to establish assert tolerance to minutes...")
        next_interval_run_at = next_interval_run_at.astimezone(pytz.utc).replace(microsecond=0).replace(second=0)
        context_next_interval_run_at = (
            context["next_interval_run_at"].astimezone(pytz.utc).replace(microsecond=0).replace(second=0)
        )

        assert next_interval_run_at == context_next_interval_run_at

    # https://docs.djangoproject.com/en/4.2/topics/testing/advanced/#example
    def test_item_list_page_renders_correctly(self, request_with_user: WSGIRequest) -> None:
        request = request_with_user
        response = ItemListView.as_view()(request)
        logger.info("Checking that the response status code is 200")
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "form_variable, form_class",
        [("form", ScrapeForm), ("scrape_interval_form", ScrapeIntervalForm)],
    )
    def test_form_variable_is_instance_of_form_class(
        self,
        form_variable: str,
        form_class: Type[ScrapeForm | ScrapeIntervalForm],
        request_with_user: WSGIRequest,
    ) -> None:
        request = request_with_user
        view = ItemListView()
        view.setup(request)

        logger.info(
            "Initializing 'object_list' attribute for '%s' view",
            view.__class__.__name__,
        )
        view.object_list = view.get_queryset()

        context = view.get_context_data()
        assert isinstance(context[form_variable], form_class)


class TestItemDetailView:
    @pytest.fixture
    def request_with_user(self) -> WSGIRequest:
        """Returns a WSGIRequest object with a logged-in user and an empty session.

        This fixture can be used to test views that require authentication.
        """
        url = reverse("item_list")
        factory = RequestFactory()
        user = User.objects.create_user(username="testuser", email="testuser@test.com", password="testpassword")
        request = factory.get(url)
        request.user = user
        request.session = {}

        return request

    @pytest.fixture
    def client(self) -> Client:
        return Client()

    @pytest.fixture
    def logged_in_user(self, client: Client) -> User:
        user = User.objects.create_user(username="loggedin", email="loggedin@test.com", password="testpassword")
        client.login(username="loggedin", password="testpassword")
        return user

    @pytest.fixture
    def item(self, logged_in_user: User) -> Item:
        return Item.objects.create(
            tenant=logged_in_user.tenant,
            name="Test Item",
            sku="12345",
            price=100,
        )

    @pytest.mark.parametrize("expected_context_item", ["item", "prices"])
    def test_item_present_in_context(
        self, request_with_user: WSGIRequest, item: Item, expected_context_item: str
    ) -> None:
        """Checks whether the expected context item ('item' or 'prices') is present
        when viewing the 'ItemDetailView' with a user-authenticated request and a provided 'item'.
        """
        request = request_with_user
        view = ItemDetailView(object=item)
        view.setup(request)

        logger.info(
            "Initializing 'object_list' attribute for '%s' view",
            view.__class__.__name__,
        )
        view.object_list = view.get_queryset()
        logger.debug("view.object_list: %s", view.object_list)

        logger.debug("view.get_context_data(): %s", view.get_context_data())
        context = view.get_context_data()
        assert expected_context_item in context

    def test_return_404_if_invalid_sku(self, client: Client, item: Item) -> None:
        invalid_url = reverse("item_detail", kwargs={"slug": "invalid-sku"})
        logger.info("Attempting to access a non-existent item with at %s", invalid_url)
        response = client.get(invalid_url)
        assert response.status_code == 404, f"Expected status code 404 but got {response.status_code}"

        valid_url = reverse("item_detail", kwargs={"slug": item.sku})
        logger.info("Attempting to access an existing item with at %s", valid_url)
        response = client.get(valid_url)
        assert response.status_code != 404, f"Expected status code not 404 but got {response.status_code}"


class TestScrapeItemsView:
    @pytest.fixture(autouse=True)
    def create_items(self, mocker) -> None:
        self.sku1 = "12345"
        self.sku2 = "67890"
        sku_data = {
            self.sku1: {
                "name": "Test Item 1",
                "priceU": 20000,
                "salePriceU": 10000,
                "basicSale": 30,
                "image": "test1.jpg",
                "category": "Test Category 1",
                "brand": "Test Brand 1",
                "seller_name": "Test Brand 1",
                "rating": 4.5,
                "feedbacks": 10,
            },
            self.sku2: {
                "name": "Test Item 2",
                "priceU": 20000,
                "salePriceU": 15000,
                "basicSale": 30,
                "image": "test2.jpg",
                "category": "Test Category 2",
                "brand": "Test Brand 2",
                "seller_name": "Test Brand 2",
                "rating": 4.2,
                "feedbacks": 8,
            },
        }

        # Create a list to store mock responses
        mock_responses = []

        for sku, data in sku_data.items():
            mock_response = httpx.Response(
                200,
                json={
                    "data": {
                        "products": [
                            {
                                "name": data["name"],
                                "id": sku,
                                "salePriceU": data["salePriceU"],
                                "priceU": data["priceU"],
                                "sale": data["basicSale"],
                                "image": data["image"],
                                "category": data["category"],
                                "brand": data["brand"],
                                "seller_name": data["seller_name"],
                                "rating": data["rating"],
                                "feedbacks": data["feedbacks"],
                                "extended": {
                                    "basicPriceU": data["salePriceU"],
                                    "basicSale": 30,
                                },
                            }
                        ]
                    },
                },
            )
            logger.debug("Item created with SKU=%s", sku)

            mock_response.request = httpx.Request(
                method="GET",
                url=f"https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={sku}",
            )

            mock_responses.append(mock_response)

        mocker.patch("httpx.get", side_effect=mock_responses)
        # To prevent the following error: "django.contrib.messages.api.MessageFailure:
        # You cannot add messages without installing django.contrib.messages.middleware.MessageMiddleware"
        mocker.patch("django.contrib.messages.success")
        mocker.patch("django.contrib.messages.error")

    @pytest.fixture
    def post_request_with_user(self) -> WSGIRequest:
        skus = f"{self.sku1}, {self.sku2}"
        # user = User.objects.create_user(username="testuser", email="testuser@test.com", password="testpassword")
        user = UserFactory(username="testuser", email="testuser@test.com", password="testpassword")
        factory = RequestFactory()
        url = reverse("scrape_item", kwargs={"skus": skus})
        request = factory.post(url, {"skus": skus})
        request.user = user

        return request

    @pytest.fixture
    def update_post_request_with_user(self) -> WSGIRequest:
        skus = f"{self.sku1}, {self.sku2}"
        user = User.objects.create_user(username="testuser", email="testuser@test.com", password="testpassword")
        factory = RequestFactory()
        url = reverse("update_items")
        request = factory.post(url, {"selected_items": skus})
        request.user = user

        return request

    def test_user_and_quotas_default_values(self):
        my_user = UserFactory()
        my_user.tenant.quota = TenantQuotaFactory()
        assert my_user.tenant.quota is not None
        assert my_user.tenant.quota.total_hours_allowed == 10
        assert my_user.tenant.quota.skus_limit == 10
        assert my_user.tenant.quota.parse_units_limit == 100

    def test_post_valid_form_redirects(self, post_request_with_user: WSGIRequest, mocker) -> None:  # type: ignore
        request = post_request_with_user
        mocker.patch("main.utils.scrape_live_price", return_value=100)
        response = scrape_items(request, f"{self.sku1}, {self.sku2}")
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."

    def test_post_valid_form_updates_items(self, post_request_with_user: WSGIRequest, mocker) -> None:  # type: ignore
        request = post_request_with_user
        mocker.patch("main.utils.scrape_live_price", return_value=100)

        logger.info("Updating items")
        scrape_items(request, f"{self.sku1}, {self.sku2}")
        logger.debug("Items updated with skus: %s, %s", self.sku1, self.sku2)
        number_of_items = Item.objects.filter(sku__in=[self.sku1, self.sku2]).count()

        logger.info("Checking if the items were updated in the database as expected")
        assert number_of_items == 2, f"Number of items should be 2, but it is {number_of_items}"

    def test_update_items_view(self, update_post_request_with_user: WSGIRequest, mocker) -> None:  # type: ignore
        request = update_post_request_with_user
        mocker.patch(
            "main.views.scrape_items_from_skus",
            return_value=([{"sku": "12345", "name": "Test Item 1"}, {"sku": "67890", "name": "Test Item 2"}], []),
        )

        logger.info("Updating items...")
        update_items(request)
        logger.debug("Items updated with skus: %s, %s", self.sku1, self.sku2)
        number_of_items = Item.objects.filter(sku__in=[self.sku1, self.sku2]).count()

        logger.info("Checking if the items were updated in the database as expected")
        assert number_of_items == 2, f"Number of items should be 2, but it is {number_of_items}"

    def test_redirect_if_no_items_selected(self, mocker):
        factory = RequestFactory()
        user = UserFactory()
        item_list_url = reverse("item_list")
        mocker.patch("main.views.is_at_least_one_item_selected", return_value=False)
        request = factory.post(item_list_url, {"selected_items": ["1", "2"]})
        request.user = user

        response = update_items(request)
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."
        assert response.url == item_list_url

    def test_message_called_if_sku_quota_exceeded(
        self, client: Client, post_request_with_user: WSGIRequest, mocker
    ) -> None:
        """
        Tests that a message is displayed to the user if the quota is exceeded and no quota change is made.
        """
        skus = ["12345", "67890"]
        request = post_request_with_user
        error_message = mocker.patch("django.contrib.messages.error")

        logger.info("Creating a user with a quota of 1 max allowed sku...")
        request.user.tenant.quota = TenantQuotaFactory()
        request.user.tenant.quota.skus_limit = 1
        old_user_quota = request.user.tenant.quota.skus_limit

        logger.info("Sending a POST request to scrape 2 SKUs...")
        response = scrape_items(request, skus)
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."
        logger.info("Checking if the error message was displayed to the user...")
        assert error_message.call_count == 1

        new_user_quota = request.user.tenant.quota.skus_limit
        logger.info("Checking if the max allowed skus were not changed after the error...")
        assert new_user_quota == old_user_quota

    def test_message_not_called_if_sku_quota_not_exceeded(
        self, client: Client, post_request_with_user: WSGIRequest, mocker
    ) -> None:
        """
        Tests that a message is not displayed to the user if the quota is not exceeded and quota change is made.
        """
        skus = ["12345", "67890"]
        request = post_request_with_user
        error_message = mocker.patch("django.contrib.messages.error")

        logger.info("Creating a user with a quota of 3 max allowed sku...")
        request.user.tenant.quota = TenantQuotaFactory()
        request.user.tenant.quota.skus_limit = 3
        old_user_quota = request.user.tenant.quota.skus_limit

        logger.info("Sending a POST request to scrape 2 SKUs...")
        response = scrape_items(request, skus)
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."

        logger.info("Checking that no error message was displayed to the user...")
        assert error_message.call_count == 0

        new_user_quota = request.user.tenant.quota.skus_limit
        logger.info("Checking if the max allowed skus was changed by the number of skus sent...")
        assert new_user_quota == old_user_quota - len(skus)

    @pytest.mark.skip(reason="Manual updates quota will be deprecated in the future")
    @pytest.mark.parametrize(
        "manual_updates_count, errors_called_count, is_quota_updated",
        [
            (0, 1, False),
            (1, 0, True),
        ],
        ids=["no_quota_left", "quota_left"],
    )
    def test_message_called_if_manual_updates_quota_exceeded(
        self,
        client: Client,
        update_post_request_with_user: WSGIRequest,
        mocker,
        manual_updates_count,
        errors_called_count,
        is_quota_updated,
    ) -> None:
        """
        Tests that a message is displayed to the user if the manual updatesquota is exceeded.
        Test flow:
        1. Create a user with a quota of manual updates.
        2. Send a POST request to update items, which should fail if quota is exceeded and not fail if quota is not exceeded.
        3. Check if the error message is displayed in case of failure.
        4. Check that manual updates quota not updated after the error and is updated in case of success.
        """
        request = update_post_request_with_user
        error_message = mocker.patch("django.contrib.messages.error")

        logger.info("Creating a user with a quota of 1 max allowed sku...")
        user_quota = TenantQuota.objects.get(user=request.user)
        user_quota.manual_updates = manual_updates_count
        user_quota.save()

        old_user_quota = user_quota.manual_updates

        logger.info("Sending a POST request to update quota...")
        response = update_items(request)
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."
        logger.info("Checking if the error message was displayed to the user...")
        assert error_message.call_count == errors_called_count

        user_quota.refresh_from_db()
        new_user_quota = user_quota.manual_updates
        logger.info("Checking if the max allowed skus were not changed after the error...")
        assert (
            new_user_quota != old_user_quota
        ) == is_quota_updated, f"Expected {old_user_quota}, but got {new_user_quota}."

    def test_message_called_if_allowed_parse_units_quota_exceeded(
        self, post_request_with_user: WSGIRequest, mocker
    ) -> None:
        """
        Tests that a message is displayed to the user if the quota is exceeded.
        Test flow:
        1. Create a user with a quota of 1 max allowed sku.
        2. Send a POST request to the scrape 2 SKUs (thus exceeding the quota).
        3. Check if the error message is displayed to the user.
        4. Check that allowed parse units were not changed after the error.
        """
        skus = ["12345", "67890"]
        request = post_request_with_user
        error_message = mocker.patch("django.contrib.messages.error")

        logger.info("Creating a user with a quota of 1 allowed parse unit...")
        request.user.tenant.quota = TenantQuotaFactory()
        request.user.tenant.quota.parse_units_limit = 1
        old_user_quota = request.user.tenant.quota.parse_units_limit

        logger.info("Sending a POST request to scrape 2 SKUs...")
        response = scrape_items(request, skus)
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."
        logger.info("Checking if the error message was displayed to the user...")
        assert error_message.call_count == 1

        new_user_quota = request.user.tenant.quota.parse_units_limit
        logger.info("Checking if the allowed parse units were not changed after the error...")
        assert new_user_quota == old_user_quota

    def test_message_not_called_if_allowed_parse_units_quota_not_exceeded(
        self, post_request_with_user: WSGIRequest, mocker
    ) -> None:
        """
        Tests that a message is displayed to the user if the quota is exceeded.
        Test flow:
        1. Create a user with a quota of 1 max allowed sku.
        2. Send a POST request to the scrape 2 SKUs (thus exceeding the quota).
        3. Check if the error message is displayed to the user.
        4. Check that allowed parse units were not changed after the error.
        """
        skus = ["12345", "67890"]
        request = post_request_with_user
        error_message = mocker.patch("django.contrib.messages.error")

        logger.info("Creating a user with a quota of 3 allowed parse unit...")
        request.user.tenant.quota = TenantQuotaFactory()
        request.user.tenant.quota.parse_units_limit = 3
        old_user_quota = request.user.tenant.quota.parse_units_limit

        logger.info("Sending a POST request to scrape 2 SKUs...")
        response = scrape_items(request, skus)
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."
        logger.info("Checking if the error message was displayed to the user...")
        assert error_message.call_count == 0

        new_user_quota = request.user.tenant.quota.parse_units_limit
        logger.info("Checking if the allowed parse units were not changed after the error...")
        assert new_user_quota != old_user_quota


class TestCreateScrapeIntervalTaskView:
    # pylint: disable=unused-argument
    # Use pytest-mock (mocker) to isolate the tests from API in case API fails or real item's info changes (e.g. price)
    @pytest.fixture(autouse=True)
    def create_items(self, mocker) -> None:  # type: ignore
        self.sku1 = "12345"
        self.name1 = "Test Item 1"
        self.sku2 = "67890"
        self.name2 = "Test Item 2"
        sku_data = {
            self.sku1: {
                "name": self.name1,
                "salePriceU": 10000,
                "image": "test1.jpg",
                "category": "Test Category 1",
                "brand": "Test Brand 1",
                "seller_name": "Test Brand 1",
                "rating": 4.5,
                "feedbacks": 10,
            },
            self.sku2: {
                "name": self.name2,
                "salePriceU": 15000,
                "image": "test2.jpg",
                "category": "Test Category 2",
                "brand": "Test Brand 2",
                "seller_name": "Test Brand 2",
                "rating": 4.2,
                "feedbacks": 8,
            },
        }

        # Create a list to store mock responses
        mock_responses = []

        for sku, data in sku_data.items():
            mock_response = httpx.Response(
                200,
                json={
                    "data": {
                        "products": [
                            {
                                "name": data["name"],
                                "id": sku,
                                "salePriceU": data["salePriceU"],
                                "image": data["image"],
                                "category": data["category"],
                                "brand": data["brand"],
                                "seller_name": data["seller_name"],
                                "rating": data["rating"],
                                "feedbacks": data["feedbacks"],
                            }
                        ]
                    },
                },
            )
            logger.debug("Item created with SKU=%s", sku)

            mock_response.request = httpx.Request(
                method="GET",
                url=f"https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={sku}",
            )

            mock_responses.append(mock_response)

        mocker.patch("httpx.get", side_effect=mock_responses)

    @pytest.fixture
    def client(self) -> Client:
        return Client()

    @pytest.fixture
    def logged_in_user(self, client: Client) -> User:
        user = User.objects.create_user(username="testuser", email="testuser@test.com", password="testpassword")
        client.login(username="testuser", password="testpassword")
        return user

    @pytest.fixture
    def valid_form_data(self) -> dict[str, Any]:
        return {
            "interval_value": 60,
            "period": "hours",
        }

    @pytest.mark.skip
    def test_task_created(self, client: Client, logged_in_user: User, valid_form_data: dict, mocker):
        mocker.patch("django.contrib.messages.error")
        client.post(reverse("create_scrape_interval"), data=valid_form_data)
        assert (
            PeriodicTask.objects.all().count() == 1
        ), f"Expected no periodic tasks to be created, but got {PeriodicTask.objects.all().count()}"

    def test_redirect_if_valid_form_data(self, client: Client, logged_in_user: User, valid_form_data: dict) -> None:
        logger.info("Sending a POST request to the view with valid form data")
        response = client.post(reverse("create_scrape_interval"), data=valid_form_data)

        # Check if the response status code is 302, indicating a successful redirect
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."
        logger.debug("Successfully redirected to %s", response.url)

    @pytest.mark.skip(reason="Skip until adjusted to the new interval behavior")
    def test_interval_task_exists_in_session(self, client: Client, logged_in_user: User, valid_form_data: dict) -> None:
        logger.info("Sending a POST request to the view with valid form data")
        client.post(reverse("create_scrape_interval"), data=valid_form_data)

        logger.info("Checking if the 'scrape_interval_task' key exists in the session")
        assert (
            "scrape_interval_task" in client.session
        ), f"Failed to find 'scrape_interval_task' key in {client.session.keys()}"

    @pytest.mark.skip
    def test_correct_interval_task_info_stored_in_session(
        self, client: Client, logged_in_user: User, valid_form_data: dict
    ) -> None:
        # pylint: disable=unused-argument
        logger.info("Sending a POST request to the view with valid form data")
        client.post(reverse("create_scrape_interval"), data=valid_form_data)

        logger.info("Extracting the stored task information from the session")
        task_info = client.session["scrape_interval_task"]
        task_interval = str(valid_form_data["interval"])
        logger.debug("Extracted task info: %s", task_info)

        assert task_info is not None
        logger.info("Checking for correct task name and interval value")
        assert (
            "scrape_interval_task_" in task_info
        ), f"Expected task name to start with 'scrape_interval_task_', but got {task_info}"
        assert task_interval in task_info

    def test_invalid_form_data_does_not_create_task(self, client: Client, logged_in_user: User) -> None:
        invalid_form_data = {"invalid_field_name": 60}
        logger.info("Sending a POST request to the view with invalid form data and expecting error")
        client.post(reverse("create_scrape_interval"), data=invalid_form_data)

        logger.debug("Periodic tasks: %s", PeriodicTask.objects.all())
        assert (
            PeriodicTask.objects.all().count() == 0
        ), f"Expected no periodic tasks to be created, but got {PeriodicTask.objects.all().count()}"

    @pytest.mark.skip(reason="Skip until adjusted to the new interval behavior")
    def test_no_items_selected_does_not_create_task(self, client, logged_in_user, mocker):
        mocker.patch("django.contrib.messages.error")
        no_items_selected = {
            "interval": 60,
            "selected_items": [],
        }
        client.post(reverse("create_scrape_interval"), data=no_items_selected)
        assert (
            PeriodicTask.objects.all().count() == 0
        ), f"Expected no periodic tasks to be created, but got {PeriodicTask.objects.all().count()}"

    def test_interval_created(self):
        interval = IntervalScheduleFactory()
        assert interval is not None

    def test_interval_fields(self):
        interval = IntervalScheduleFactory(every=10, period="seconds")
        assert interval.every == 10
        assert interval.period == "seconds"

    def test_pediodic_task_created(self):
        task = PeriodicTaskFactory()
        assert task is not None

    def test_periodic_task_fields(self):
        task = PeriodicTaskFactory(interval=IntervalScheduleFactory(every=10, period="seconds"), args=["arg1", 1])
        assert task.interval.every == 10
        assert task.interval.period == "seconds"
        assert task.args == ["arg1", 1]


class TestUpdateScrapeInterval:
    def test_update_task_args(self):
        task = PeriodicTaskFactory(
            interval=IntervalScheduleFactory(every=10, period="seconds"), args=["tenant_1", ["item_1", "item_2"]]
        )
        task.args = ["tenant_1", ["item_1", "item_2", "item_3"]]
        task.save()
        assert task.args == ["tenant_1", ["item_1", "item_2", "item_3"]]

    def test_update_scrape_interval_post_success(self):
        user = UserFactory()
        PeriodicTaskFactory(
            name=task_name(user),
        )
        data = {"selected_items": ["1", "2"]}
        request = RequestFactory().post(reverse("update_scrape_interval"), data)
        request.user = user

        response = update_scrape_interval(request)

        assert response.status_code == 302
        assert response.url == reverse("item_list")

    def test_invalid_form_invokes_error_message(self, mocker):
        message = mocker.patch("django.contrib.messages.error")
        user = UserFactory()
        PeriodicTaskFactory(name=task_name(user))
        request = RequestFactory().post(reverse("update_scrape_interval"), {"invalid_key": "invalid_value"})
        request.user = user

        response = update_scrape_interval(request)
        assert (
            message.call_count == 1
        ), f"Expected 1 message to be displayed, but {message.call_count} were displayed instead"
        assert response.status_code == 302

    def test_update_scrape_interval_no_task_found(self):
        user = UserFactory()
        request = RequestFactory().post(reverse("update_scrape_interval"), {})
        request.user = user

        with pytest.raises(Http404):
            update_scrape_interval(request)


class TestDestroyScrapeIntervalTaskView:
    @pytest.fixture
    def client(self) -> Client:
        return Client()

    @pytest.fixture
    def valid_form_data(self) -> dict[str, Any]:
        return {
            "interval": 60,
            "selected_items": [1, 2],
        }

    @pytest.fixture
    def post_request_with_user(self, client: Client) -> WSGIRequest:
        user = User.objects.create_user(username="testuser", email="testuser@test.com", password="testpassword")
        factory = RequestFactory()
        url = reverse("destroy_scrape_interval")
        request = factory.post(url)
        request.user = user
        client.login(username="testuser", password="testpassword")

        return request

    @pytest.mark.skip
    def test_post_valid_form_redirects(
        self, client: Client, valid_form_data: dict, post_request_with_user: WSGIRequest
    ) -> None:
        logger.info("Creating an interval task")
        client.post(reverse("create_scrape_interval"), data=valid_form_data)
        request = post_request_with_user
        request.session = {}

        redirect_destination_url = reverse("item_list")
        response = destroy_scrape_interval_task(request)

        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."
        assert (
            response.url == redirect_destination_url
        ), f"Expected redirect to {redirect_destination_url}, but got {response.url}"

    @pytest.mark.skip
    def test_interval_task_not_in_session(
        self, client: Client, post_request_with_user: WSGIRequest, valid_form_data: dict
    ) -> None:
        # pylint: disable=unused-argument
        logger.info("Creating an interval task")
        client.post(reverse("create_scrape_interval"), data=valid_form_data)

        task_info = client.session["scrape_interval_task"]

        logger.info("Deleting the interval task")
        client.post(reverse("destroy_scrape_interval"), data=valid_form_data)
        assert "scrape_interval_task" not in client.session, (
            "Found 'scrape_interval_task' key in session keys, but it should not exist. "
            f"Session keys: {client.session.keys()}"
        )
        logger.debug("Interval task was successfully deleted (%s)", task_info)

    def test_redirect_when_deleting_non_existing_task(
        self, client: Client, post_request_with_user: WSGIRequest
    ) -> None:
        # pylint: disable=unused-argument
        response = client.post(reverse("destroy_scrape_interval"))
        assert response.status_code == 302
