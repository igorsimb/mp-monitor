import logging
from typing import Type, Any

import httpx
import pytest
from django.contrib.auth import get_user_model
from django.core.handlers.wsgi import WSGIRequest
from django.test import RequestFactory, Client
from django.urls import reverse, NoReverseMatch
from django_celery_beat.models import PeriodicTask

from main.forms import ScrapeForm, ScrapeIntervalForm
from main.models import Item
from main.views import ItemListView, ItemDetailView, scrape_items, destroy_scrape_interval_task

logger = logging.getLogger(__name__)

User = get_user_model()

pytestmark = [pytest.mark.django_db]


class TestItemListView:
    context_object_list = ["items", "sku", "form", "scrape_interval_form", "scrape_interval_task"]

    @pytest.fixture
    def request_with_user(self) -> WSGIRequest:
        """
        Returns a WSGIRequest object with a logged-in user and an empty session.
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
    def test_item_present_in_context(self, request_with_user: WSGIRequest, expected_context_item: str) -> None:
        request = request_with_user

        view = ItemListView()
        view.setup(request)

        logger.info("Initializing 'object_list' attribute for '%s' view", view.__class__.__name__)
        view.object_list = view.get_queryset()
        logger.debug("view.object_list = %s", view.object_list)

        context = view.get_context_data()
        assert expected_context_item in context

    # https://docs.djangoproject.com/en/4.2/topics/testing/advanced/#example
    def test_item_list_page_renders_correctly(self, request_with_user: WSGIRequest) -> None:
        request = request_with_user
        response = ItemListView.as_view()(request)
        logger.info("Checking that the response status code is 200")
        assert response.status_code == 200

    @pytest.mark.parametrize(
        "form_variable, form_class", [("form", ScrapeForm), ("scrape_interval_form", ScrapeIntervalForm)]
    )
    def test_form_variable_is_instance_of_form_class(
        self, form_variable: str, form_class: Type[ScrapeForm | ScrapeIntervalForm], request_with_user: WSGIRequest
    ) -> None:
        request = request_with_user
        view = ItemListView()
        view.setup(request)

        logger.info("Initializing 'object_list' attribute for '%s' view", view.__class__.__name__)
        view.object_list = view.get_queryset()

        context = view.get_context_data()
        assert isinstance(context[form_variable], form_class)


class TestItemDetailView:
    @pytest.fixture
    def request_with_user(self) -> WSGIRequest:
        """
        Returns a WSGIRequest object with a logged-in user and an empty session.
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
        """
        Checks whether the expected context item ('item' or 'prices') is present
        when viewing the 'ItemDetailView' with a user-authenticated request and a provided 'item'.
        """
        request = request_with_user
        view = ItemDetailView(object=item)
        view.setup(request)

        logger.info("Initializing 'object_list' attribute for '%s' view", view.__class__.__name__)
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
                "salePriceU": 10000,
                "image": "test1.jpg",
                "category": "Test Category 1",
                "brand": "Test Brand 1",
                "seller_name": "Test Brand 1",
                "rating": 4.5,
                "feedbacks": 10,
            },
            self.sku2: {
                "name": "Test Item 2",
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
                method="GET", url=f"https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={sku}"
            )

            mock_responses.append(mock_response)

        mocker.patch("httpx.get", side_effect=mock_responses)
        # To prevent the following error: "django.contrib.messages.api.MessageFailure:
        # You cannot add messages without installing django.contrib.messages.middleware.MessageMiddleware"
        mocker.patch("django.contrib.messages.success")

    @pytest.fixture
    def post_request_with_user(self) -> WSGIRequest:
        skus = f"{self.sku1}, {self.sku2}"
        user = User.objects.create_user(username="testuser", email="testuser@test.com", password="testpassword")
        factory = RequestFactory()
        url = reverse("scrape_item", kwargs={"skus": skus})
        request = factory.post(url, {"skus": skus})
        request.user = user

        return request

    def test_post_valid_form_redirects(self, post_request_with_user: WSGIRequest) -> None:
        request = post_request_with_user
        response = scrape_items(request, f"{self.sku1}, {self.sku2}")
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."

    def test_post_valid_form_updates_items(self, post_request_with_user: WSGIRequest) -> None:
        request = post_request_with_user

        logger.info("Updating items")
        scrape_items(request, f"{self.sku1}, {self.sku2}")
        logger.debug("Items updated with skus: %s, %s", self.sku1, self.sku2)
        number_of_items = Item.objects.filter(sku__in=[self.sku1, self.sku2]).count()

        logger.info("Checking if the items were updated in the database as expected")
        assert number_of_items == 2, f"Number of items should be 2, but it is {number_of_items}"


class TestCreateScrapeIntervalTaskView:
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
                method="GET", url=f"https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={sku}"
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
            "interval": 60,
            "selected_items": [1, 2],
        }

    def test_redirect_if_valid_form_data(self, client: Client, logged_in_user: User, valid_form_data: dict) -> None:
        # pylint: disable=unused-argument
        logger.info("Sending a POST request to the view with valid form data")
        response = client.post(reverse("create_scrape_interval"), data=valid_form_data)

        # Check if the response status code is 302, indicating a successful redirect
        assert response.status_code == 302, f"Expected status code 302, but got {response.status_code}."
        logger.debug("Successfully redirected to %s", response.url)

    def test_interval_task_exists_in_session(self, client: Client, logged_in_user: User, valid_form_data: dict) -> None:
        # pylint: disable=unused-argument
        logger.info("Sending a POST request to the view with valid form data")
        client.post(reverse("create_scrape_interval"), data=valid_form_data)

        logger.info("Checking if the 'scrape_interval_task' key exists in the session")
        assert (
            "scrape_interval_task" in client.session
        ), f"Failed to find 'scrape_interval_task' key in {client.session.keys()}"

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

    def test_invalid_form_data_does_not_create_task(self, client: Client) -> None:
        invalid_form_data = {"invalid_field_name": 60}
        with pytest.raises(NoReverseMatch):
            logger.info("Sending a POST request to the view with invalid form data and expecting error")
            client.post(reverse("create_scrape_interval"), data=invalid_form_data)

        logger.debug("Periodic tasks: %s", PeriodicTask.objects.all())
        assert (
            PeriodicTask.objects.all().count() == 0
        ), f"Expected no periodic tasks to be created, but got {PeriodicTask.objects.all().count()}"


class TestDestroyScrapeIntervalTaskView:
    # At the moment Interval Task can be created without active items. This will be changed in future and,
    # as a result, create_items fixture will need to be used.
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
            f"Found 'scrape_interval_task' key in session keys, but it should not exist. "
            f"Session keys: {client.session.keys()}"
        )
        logger.debug("Interval task was successfully deleted (%s)", task_info)

    def test_interval_task_does_not_exist_exception(self, client: Client, post_request_with_user: WSGIRequest) -> None:
        # pylint: disable=unused-argument
        with pytest.raises(PeriodicTask.DoesNotExist):
            client.post(reverse("destroy_scrape_interval"))
