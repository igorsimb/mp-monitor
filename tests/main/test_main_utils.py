import logging
from unittest.mock import Mock

import httpx
import pytest
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.utils.safestring import mark_safe
from pytest_mock import MockerFixture

from main.models import Item, Tenant
from main.utils import (
    uncheck_all_boxes,
    scrape_item,
    show_successful_scrape_message,
    MAX_ITEMS_ON_SCREEN,
    is_at_least_one_item_selected,
    scrape_items_from_skus,
    update_or_create_items,
)

pytestmark = [pytest.mark.django_db]

logger = logging.getLogger(__name__)

User = get_user_model()


class TestUncheckAllBoxes:
    @pytest.fixture
    def user(self):
        user = User.objects.create(username="test_user", email="test_email@test.com")
        return user

    @pytest.fixture
    def tenant(self, user):
        tenant = Tenant.objects.get(name=user.email)
        return tenant

    def test_update_all_items(self, request, user, tenant):
        number_of_items = 3

        logger.info("Creating %s items for tenant '%s'", number_of_items, tenant)
        items = [
            Item.objects.create(tenant=tenant, name=f"Item {i}", sku=f"1234{i}", is_parser_active=True)
            for i in range(1, number_of_items + 1)
        ]

        request.user = user
        logger.info("Calling uncheck_all_boxes() for tenant '%s'", tenant)
        uncheck_all_boxes(request)

        logger.info("Checking that all items for tenant '%s' are updated with is_parser_active=False", tenant)
        for item in items:
            item.refresh_from_db()
            logger.debug("'%s' is_parser_active=%s", item.name, item.is_parser_active)
            assert not item.is_parser_active

    def test_no_items_exist(self, request, user, tenant):
        """Test if uncheck_all_boxes handles the case when no items exist for the user's tenant."""
        request.user = user
        logger.info("Calling uncheck_all_boxes() with no items")
        uncheck_all_boxes(request)

        assert Item.objects.filter(tenant=tenant).count() == 0

    def test_uncheck_for_one_tenant_when_multiple_tenants_exist(self, request):
        """Multiple tenants exist, but only items for the user's tenant are updated."""
        logger.info("Creating 2 users and getting tenants")
        user1 = User.objects.create(username="user1", email="user1_email@test.com")
        logger.debug("User '%s' created", user1)
        user2 = User.objects.create(username="user2", email="user2_email@test.com")
        logger.debug("User '%s' created", user2)
        tenant1 = Tenant.objects.get(name=user1.email)
        logger.debug("Tenant '%s' created", tenant1)
        tenant2 = Tenant.objects.get(name=user2.email)
        logger.debug("Tenant '%s' created", tenant2)

        logger.info("Creating items for both tenants")
        item1 = Item.objects.create(tenant=tenant1, name="Item 1", sku="12345", is_parser_active=True)
        logger.debug("Item '%s' created", item1)
        item2 = Item.objects.create(tenant=tenant2, name="Item 2", sku="67899", is_parser_active=True)
        logger.debug("Item '%s' created", item2)

        logger.info("Calling uncheck_all_boxes() for tenant '%s'", tenant1)
        request.user = user1
        uncheck_all_boxes(request)

        logger.info("Checking that only item1 for tenant '%s' is updated with is_parser_active=False", tenant1)
        item1.refresh_from_db()
        item2.refresh_from_db()
        assert not item1.is_parser_active, f"Item1 is_parser_active should be False but it is {item1.is_parser_active}"
        assert item2.is_parser_active, f"Item2 is_parser_active should be True but it is {item2.is_parser_active}"

    def test_no_items_updated_if_user_not_authenticated(self, request):
        with pytest.raises(AttributeError):
            logger.info("Expecting %s when calling uncheck_all_boxes() without authentication", AttributeError)
            uncheck_all_boxes(request)

        logger.info("Checking that no items are updated")
        assert Item.objects.filter(is_parser_active=True).count() == 0

    def test_uncheck_all_boxes_already_inactive(self, request, user, tenant):
        """Test if the function handles items with is_parser_active=False gracefully."""
        Item.objects.create(name="InactiveItem1", tenant=tenant, sku="12345", is_parser_active=False)
        Item.objects.create(name="InactiveItem2", tenant=tenant, sku="67899", is_parser_active=False)

        request.user = user
        uncheck_all_boxes(request)

        inactive_items = Item.objects.filter(tenant=tenant, is_parser_active=False)
        for item in inactive_items:
            assert (
                not item.is_parser_active
            ), f"Item {item.name} is_parser_active should be False but it is {item.is_parser_active}"


class TestScrapeItem:
    # Use pytest-mock (mocker) to isolate the tests from API in case API fails or real item's info changes (e.g. price)
    @pytest.fixture(autouse=True)
    def setup(self, mocker):
        self.name = "Test Item"
        self.sku = "12345"
        self.price = 10000
        self.mock_response = httpx.Response(
            200,
            json={
                "data": {
                    "products": [
                        {
                            "id": self.sku,
                            "name": self.name,
                            "priceU": self.price,
                            "salePriceU": self.price,
                            "live_price": self.price,
                            "basicSale": 30,
                            "sale": 30,
                            "image": "test.jpg",
                            "category": "Test Category",
                            "brand": "Test Brand",
                            "seller_name": "Test Brand",
                            "rating": 4.5,
                            "feedbacks": 10,
                            "extended": {
                                "basicPriceU": self.price,
                                "basicSale": 30,
                            },
                        },
                    ]
                }
            },
        )

        self.mock_response.request = httpx.Request(
            method="GET", url=f"https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={self.sku}"
        )

        mocker.patch("httpx.get", return_value=self.mock_response)
        mocker.patch("main.utils.scrape_live_price", return_value=self.price / 100)

    def test_retrieve_data_from_mock_api(self):
        logger.info("Calling scrape_item() with a mock SKU (%s)", self.sku)
        result = scrape_item(self.sku)

        logger.info("Checking that the result is the expected parsed item dictionary")
        assert result == {
            "name": "Test Item",
            "sku": self.sku,
            "price": 100.0,
            "seller_price": 70.0,
            "spp": -43,
            "image": "test.jpg",
            "is_in_stock": True,
            "category": "Test Category",
            "brand": "Test Brand",
            "seller_name": "Test Brand",
            "rating": 4.5,
            "num_reviews": 10,
        }

    def test_retry_request_on_http_error(self, mocker):
        mocker.patch(
            "httpx.get",
            side_effect=[
                httpx.HTTPError(message="Expected Error"),
                httpx.HTTPError(message="Expected Error"),
                self.mock_response,
            ],
        )

        logger.info("Calling scrape_item() with a mock SKU (%s)", self.sku)
        result = scrape_item(self.sku)

        logger.info("Checking that the result is the expected parsed item dictionary")
        assert result == {
            "name": "Test Item",
            "sku": self.sku,
            "price": 100,
            "seller_price": 70.0,
            "spp": -43,
            "image": "test.jpg",
            "is_in_stock": True,
            "category": "Test Category",
            "brand": "Test Brand",
            "seller_name": "Test Brand",
            "rating": 4.5,
            "num_reviews": 10,
        }

    def test_return_none_for_invalid_price_format(self):
        response_data = self.mock_response.json()

        logger.info("Assigning invalid price format to the priceU field")
        response_data["data"]["products"][0]["priceU"] = "invalidprice"

        logger.info("Returning the modified response_data dictionary: %s", response_data)
        self.mock_response.json = lambda: response_data

        logger.info("Calling scrape_item() with a mock SKU (%s)", self.sku)
        result = scrape_item(self.sku)

        logger.info("Checking that the resulting price is None")
        assert result["seller_price"] is None


class TestShowSuccessfulScrapeMessage:
    @staticmethod
    def create_items_data(num_items: int) -> list[dict]:
        return [{"name": f"Item {i}", "sku": str(10000 + i)} for i in range(1, num_items + 1)]

    @pytest.fixture
    def mock_request(self, mocker: MockerFixture) -> HttpRequest:
        mocker.patch("django.contrib.messages.success")
        return HttpRequest()

    def test_message_one_item_scraped(self, mock_request: HttpRequest) -> None:
        logger.info("Creating 1 item")
        items_data = self.create_items_data(1)

        show_successful_scrape_message(mock_request, items_data)
        expected_message = f'Обновлена информация по товару: "{items_data[0]["name"]} ({items_data[0]["sku"]})"'
        messages.success.assert_called_once_with(mock_request, expected_message)

    def test_message_multiple_items_scraped_max(self, mock_request: HttpRequest) -> None:
        logger.info("Creating %s items", MAX_ITEMS_ON_SCREEN)
        items_data = self.create_items_data(MAX_ITEMS_ON_SCREEN)

        show_successful_scrape_message(mock_request, items_data)
        expected_message = mark_safe(
            "Обновлена информация по товарам: <ul>"
            + "".join([f'<li>{item["sku"]}: {item["name"]}</li>' for item in items_data])
            + "</ul>"
        )

        messages.success.assert_called_once_with(mock_request, expected_message)

    def test_message_multiple_items_scraped_less_than_max(self, mock_request: HttpRequest) -> None:
        logger.info("Creating %s items", (MAX_ITEMS_ON_SCREEN - 1))
        items_data = self.create_items_data(MAX_ITEMS_ON_SCREEN - 1)

        show_successful_scrape_message(mock_request, items_data)
        expected_message = mark_safe(
            "Обновлена информация по товарам: <ul>"
            + "".join([f'<li>{item["sku"]}: {item["name"]}</li>' for item in items_data])
            + "</ul>"
        )
        assert len(items_data) < MAX_ITEMS_ON_SCREEN
        messages.success.assert_called_once_with(mock_request, expected_message)

    def test_message_multiple_items_scraped_more_than_max(self, mock_request: HttpRequest) -> None:
        logger.info("Creating %s items", (MAX_ITEMS_ON_SCREEN + 1))
        items_data = self.create_items_data(MAX_ITEMS_ON_SCREEN + 1)

        show_successful_scrape_message(mock_request, items_data)
        messages.success.assert_called_once_with(mock_request, f"Обновлена информация по {len(items_data)} товарам")

    def test_no_items_scraped(self, mock_request: HttpRequest, mocker) -> None:
        items_data = []
        mocker.patch("django.contrib.messages.error")
        show_successful_scrape_message(mock_request, items_data)
        messages.error.assert_called_once_with(mock_request, "Добавьте хотя бы 1 товар")


class TestAtLeastOneItemSelected:
    @pytest.fixture
    def mock_request(self, mocker: MockerFixture) -> HttpRequest:
        mocker.patch("django.contrib.messages.error")
        return HttpRequest()

    def test_at_least_one_item_selected_message(self, mock_request: HttpRequest) -> None:
        selected_item_ids = []
        is_at_least_one_item_selected(mock_request, selected_item_ids)
        messages.error.assert_called_once_with(mock_request, "Выберите хотя бы 1 товар")

    def test_no_items_selected_returns_false(self, mock_request: HttpRequest) -> None:
        selected_item_ids = []
        response = is_at_least_one_item_selected(mock_request, selected_item_ids)

        logger.info("Checking that return value is False")
        assert response is False
        logger.debug("Return value is False")

    @pytest.mark.parametrize("selected_item_ids", [["1"], ["1", "2"], ["1", "2", "3"]], ids=["1", "2", "3"])
    def test_many_item_selected_returns_true(self, selected_item_ids, mock_request: HttpRequest, mocker) -> None:
        mocker.patch("django.contrib.messages.error")
        response = is_at_least_one_item_selected(mock_request, selected_item_ids)

        logger.info("Checking that return value is True")
        assert response is True
        logger.debug("Return value is True")


class FixtureRequest:
    pass


class TestScrapeItemsFromSKUs:
    # pylint: disable=unused-argument
    @pytest.fixture
    def mock_scrape_item(self, mocker) -> Mock:
        return mocker.patch("main.utils.scrape_item", return_value={"sku": "test"})

    def test_with_valid_skus(self, mock_scrape_item: Mock) -> None:
        skus = "sku1 sku2 sku3"
        result = scrape_items_from_skus(skus)
        logger.info("Result: %s", result)
        assert result == [{"sku": "test"}, {"sku": "test"}, {"sku": "test"}]

    def test_with_skus_separated_by_commas_and_spaces(self, mock_scrape_item: Mock) -> None:
        skus = "sku1, sku2, sku3 sku4\nsku5"
        result = scrape_items_from_skus(skus)
        logger.info("Result: %s", result)
        assert result == [{"sku": "test"}, {"sku": "test"}, {"sku": "test"}, {"sku": "test"}, {"sku": "test"}]


class TestUpdateOrCreateItems:
    @pytest.fixture
    def user(self):
        user = User.objects.create(username="test_user", email="test_email@test.com")
        return user

    @pytest.fixture
    def tenant(self, user) -> Tenant:
        tenant = Tenant.objects.get(name=user.email)
        return tenant

    def test_existing_item_updated_and_not_created(self, request, user, tenant):
        request.user = user
        item_data = {"sku": "123", "name": "Test Item"}
        Item.objects.create(tenant=tenant, sku="123", name="Original Item")

        logger.info("Calling update_or_create_items() with a mock item_data dictionary")
        update_or_create_items(request, [item_data])

        item = Item.objects.get(sku="123")
        assert item.name == "Test Item"

    def test_new_item_created(self, request, user):
        request.user = user
        item_data = {"sku": "456", "name": "New Item"}
        update_or_create_items(request, [item_data])

        item = Item.objects.get(sku="456")
        assert item.name == "New Item"

    def test_update_or_create_multiple_items(self, request, user):
        request.user = user
        Item.objects.create(tenant=user.tenant, sku="111", name="Original 1")

        item_data = [
            {"sku": "111", "name": "Item 1"},
            {"sku": "222", "name": "Item 2"},
        ]
        update_or_create_items(request, item_data)

        item1 = Item.objects.get(sku="111")
        item2 = Item.objects.get(sku="222")

        logger.info("Checking that the original item was updated")
        assert item1.name != "Original 1"
        assert item1.name == "Item 1"

        logger.info("Checking that a new item was created")
        assert item2.name == "Item 2"
