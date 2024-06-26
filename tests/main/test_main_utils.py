import logging
from unittest.mock import Mock

import httpx
import pytest
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.test import RequestFactory
from django.utils.safestring import mark_safe
from factories import ItemFactory, UserFactory, PeriodicTaskFactory, IntervalScheduleFactory
from pytest_mock import MockerFixture

import config
from main.exceptions import InvalidSKUException, QuotaExceededException
from main.models import Item, Tenant
from main.utils import (
    uncheck_all_boxes,
    scrape_item,
    show_successful_scrape_message,
    is_at_least_one_item_selected,
    scrape_items_from_skus,
    update_or_create_items,
    is_sku_format_valid,
    show_invalid_skus_message,
    activate_parsing_for_selected_items,
    get_interval_russian_translation,
    update_user_quota_for_scheduled_updates,
)

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

        logger.info(
            "Checking that all items for tenant '%s' are updated with is_parser_active=False",
            tenant,
        )
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

        logger.info(
            "Checking that only item1 for tenant '%s' is updated with is_parser_active=False",
            tenant1,
        )
        item1.refresh_from_db()
        item2.refresh_from_db()
        assert not item1.is_parser_active, f"Item1 is_parser_active should be False but it is {item1.is_parser_active}"
        assert item2.is_parser_active, f"Item2 is_parser_active should be True but it is {item2.is_parser_active}"

    def test_no_items_updated_if_user_not_authenticated(self, request):
        with pytest.raises(AttributeError):
            logger.info(
                "Expecting %s when calling uncheck_all_boxes() without authentication",
                AttributeError,
            )
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
        self.sku_no_stock = "67890"
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
                            "sizes": [{"stocks": ["3"]}],
                        },
                    ]
                }
            },
        )

        self.mock_response.request = httpx.Request(
            method="GET",
            url=f"https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={self.sku}",
        )

        mocker.patch("httpx.get", return_value=self.mock_response)
        mocker.patch("main.utils.scrape_live_price", return_value=self.price / 100)

    @pytest.fixture
    def item_with_empty_stock(self, mocker: MockerFixture):
        self.sku_no_stock = "67890"
        self.price = 10000
        self.mock_response2 = httpx.Response(
            200,
            json={
                "data": {
                    "products": [
                        {
                            "id": self.sku_no_stock,
                            "priceU": self.price,
                            "salePriceU": self.price,
                            "sale": 30,
                            "sizes": [{"stocks": []}],
                        },
                    ]
                }
            },
        )
        self.mock_response2.request = httpx.Request(
            method="GET",
            url=f"https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={self.sku}",
        )
        mocker.patch("httpx.get", return_value=self.mock_response2)
        mocker.patch("main.utils.scrape_live_price", return_value=self.price / 100)

    def test_retrieve_data_from_mock_api(self):
        logger.info("Calling scrape_item() with a mock SKU (%s)", self.sku)
        result = scrape_item(self.sku)
        logger.debug("Result: %s", result)

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

    def test_item_not_in_stock(self, item_with_empty_stock: None) -> None:  # pylint: disable=unused-argument
        logger.info("Calling scrape_item() with a mock SKU (%s)", self.sku_no_stock)
        result = scrape_item(self.sku_no_stock)
        logger.info("Checking that the item is not in stock")
        assert result["is_in_stock"] is False, f"Incorrect value for Item: {result}"

    def test_retry_request_on_http_error(self, mocker) -> None:
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

    @pytest.mark.parametrize(
        "sku, expected_result",
        [("12345", True), ("abcdef", False)],
        ids=["valid_sku", "invalid_sku"],
    )
    def test_is_sku_format_valid(self, sku: str, expected_result: bool) -> None:
        """Tests the is_sku_format_valid function with various SKUs."""
        assert is_sku_format_valid(sku) == expected_result

    def test_invalid_sku_format_raises_exception(self) -> None:
        invalid_sku = "invalidsku"

        with pytest.raises(InvalidSKUException) as e:
            scrape_item(invalid_sku)

        assert e.value.sku == invalid_sku

    def test_non_existing_sku_raises_exception(self) -> None:
        """Tests that the correct exception is raised when a non-existing SKU with a valid format is provided.

        Wildberries API responses typically include an empty list of products for non-existing SKUs.
        This test verifies that `scrape_item()` calls `is_item_exists()` to check for this condition
        and raises the expected exception if the item is not found.
        """
        non_existing_sku = "11111"
        mock_empty_response = self.mock_response.json()

        logger.info("Mocking the request to return an empty list for item..")
        mock_empty_response["data"]["products"] = []
        self.mock_response.json = lambda: mock_empty_response

        logger.info("Calling scrape_item() with a non-existing SKU (%s)", non_existing_sku)
        with pytest.raises(InvalidSKUException) as e:
            scrape_item(non_existing_sku)

        assert e.value.sku == non_existing_sku


class TestMessages:
    @staticmethod
    def create_items_data(num_items: int) -> list[dict]:
        return [{"name": f"Item {i}", "sku": str(10000 + i)} for i in range(1, num_items + 1)]

    @pytest.fixture
    def mock_success_message_request(self, mocker: MockerFixture) -> HttpRequest:
        mocker.patch("django.contrib.messages.success")
        return HttpRequest()

    @pytest.fixture
    def mock_warning_message_request(self, mocker: MockerFixture) -> HttpRequest:
        mocker.patch("django.contrib.messages.warning")
        return HttpRequest()


class TestShowSuccessfulScrapeMessage(TestMessages):
    def test_message_one_item_scraped(self, mock_success_message_request: HttpRequest) -> None:
        logger.info("Creating 1 item")
        items_data = self.create_items_data(1)

        show_successful_scrape_message(mock_success_message_request, items_data)
        expected_message = f'Обновлена информация по товару: "{items_data[0]["name"]} ({items_data[0]["sku"]})"'
        messages.success.assert_called_once_with(mock_success_message_request, expected_message)

    def test_message_multiple_items_scraped_max(self, mock_success_message_request: HttpRequest) -> None:
        logger.info("Creating %s items", config.MAX_ITEMS_ON_SCREEN)
        items_data = self.create_items_data(config.MAX_ITEMS_ON_SCREEN)

        show_successful_scrape_message(mock_success_message_request, items_data)
        expected_message = mark_safe(
            "Обновлена информация по товарам: <ul>"
            + "".join([f'<li>{item["sku"]}: {item["name"]}</li>' for item in items_data])
            + "</ul>"
        )

        messages.success.assert_called_once_with(mock_success_message_request, expected_message)

    def test_message_multiple_items_scraped_less_than_max(self, mock_success_message_request: HttpRequest) -> None:
        logger.info("Creating %s items", (config.MAX_ITEMS_ON_SCREEN - 1))
        items_data = self.create_items_data(config.MAX_ITEMS_ON_SCREEN - 1)

        show_successful_scrape_message(mock_success_message_request, items_data)
        expected_message = mark_safe(
            "Обновлена информация по товарам: <ul>"
            + "".join([f'<li>{item["sku"]}: {item["name"]}</li>' for item in items_data])
            + "</ul>"
        )
        assert len(items_data) < config.MAX_ITEMS_ON_SCREEN
        messages.success.assert_called_once_with(mock_success_message_request, expected_message)

    def test_message_multiple_items_scraped_more_than_max(self, mock_success_message_request: HttpRequest) -> None:
        logger.info("Creating %s items", (config.MAX_ITEMS_ON_SCREEN + 1))
        items_data = self.create_items_data(config.MAX_ITEMS_ON_SCREEN + 1)

        show_successful_scrape_message(mock_success_message_request, items_data)
        messages.success.assert_called_once_with(
            mock_success_message_request,
            f"Обновлена информация по {len(items_data)} товарам",
        )

    def test_no_items_scraped(self, mock_success_message_request: HttpRequest, mocker) -> None:
        items_data = []
        mocker.patch("django.contrib.messages.error")
        show_successful_scrape_message(mock_success_message_request, items_data)
        messages.error.assert_called_once_with(
            mock_success_message_request,
            "Добавьте хотя бы 1 товар с корректным артикулом",
        )


class TestShowInvalidSkusMessage(TestMessages):
    def test_message_one_invalid_item(self, mock_warning_message_request: HttpRequest) -> None:
        invalid_sku = ["11111"]
        show_invalid_skus_message(mock_warning_message_request, invalid_sku)
        expected_message = mark_safe(
            f"Не удалось добавить следующий артикул: {', '.join(invalid_sku)}<br>"
            "Возможен неверный формат артикула, или товара с таким артикулом не существует. "
            "Пожалуйста, проверьте его корректность и при возникновении вопросов обратитесь в службу поддержки.",
        )
        messages.warning.assert_called_once_with(mock_warning_message_request, expected_message)

    def test_message_multiple_invalid_items(self, mock_warning_message_request: HttpRequest) -> None:
        invalid_skus = ["11111", "22222", "33333"]
        show_invalid_skus_message(mock_warning_message_request, invalid_skus)
        expected_message = mark_safe(
            f"Не удалось добавить следующие артикулы: {', '.join(invalid_skus)}<br>"
            "Возможен неверный формат артикулов, или товаров с такими артикулами не существует. "
            "Пожалуйста, проверьте их корректность и при возникновении вопросов обратитесь в службу поддержки.",
        )
        messages.warning.assert_called_once_with(mock_warning_message_request, expected_message)


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
        """
        Test that scrape_items_from_skus() calls scrape_item() with each SKU
        and correctly appends to the items_data list.
        """
        skus = "sku1 sku2 sku3"
        result = scrape_items_from_skus(skus)
        assert result == ([{"sku": "test"}, {"sku": "test"}, {"sku": "test"}], [])

    def test_exception_appends_invalid_skus_list(self, mock_scrape_item) -> None:
        """
        Test that InvalidSKUException appends SKUs to the invalid_skus list.
        """
        skus = "bad_sku1 bad_sku2"
        mock_scrape_item.side_effect = InvalidSKUException("Invalid SKUs", skus)
        result = scrape_items_from_skus(skus)
        assert result == ([], ["bad_sku1 bad_sku2", "bad_sku1 bad_sku2"])

    def test_with_skus_separated_by_commas_and_spaces(self, mock_scrape_item: Mock) -> None:
        skus = "sku1, sku2, sku3 sku4\nsku5"
        result = scrape_items_from_skus(skus)
        assert result == (
            [
                {"sku": "test"},
                {"sku": "test"},
                {"sku": "test"},
                {"sku": "test"},
                {"sku": "test"},
            ],
            [],
        )


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


class TestActivateParsingForSelectedItems:
    def test_only_affected_items_updated(self):
        user = UserFactory()
        items_to_activate = ItemFactory.create_batch(3, tenant=user.tenant)
        other_items = ItemFactory.create_batch(2, tenant=user.tenant)

        request = RequestFactory()
        request.user = user

        skus_list = [item.sku for item in items_to_activate]

        logger.info("Checking that parser is False by default")
        for sku in skus_list:
            assert not Item.objects.get(sku=sku).is_parser_active

        activate_parsing_for_selected_items(request, skus_list)

        logger.info("Checking that parser is True after calling activate_parsing_for_selected_items()")
        for sku in skus_list:
            assert Item.objects.get(sku=sku).is_parser_active

        logger.info("Checking that other items are not affected...")
        for item in other_items:
            assert not Item.objects.get(sku=item.sku).is_parser_active


class TestGetIntervalRussianTranslation:
    @pytest.mark.parametrize(
        "every,period,expected",
        [
            (1, "seconds", "каждую секунду"),
            (2, "seconds", "каждые 2 секунды"),
            (5, "seconds", "каждые 5 секунд"),
            (21, "seconds", "каждую 21 секунду"),
            (22, "seconds", "каждые 22 секунды"),
            (25, "seconds", "каждые 25 секунд"),
            (1, "minutes", "каждую минуту"),
            (2, "minutes", "каждые 2 минуты"),
            (5, "minutes", "каждые 5 минут"),
            (21, "minutes", "каждую 21 минуту"),
            (22, "minutes", "каждые 22 минуты"),
            (25, "minutes", "каждые 25 минут"),
            (1, "hours", "каждый час"),
            (2, "hours", "каждые 2 часа"),
            (5, "hours", "каждые 5 часов"),
            (21, "hours", "каждый 21 час"),
            (22, "hours", "каждые 22 часа"),
            (25, "hours", "каждые 25 часов"),
            (1, "days", "каждый день"),
            (2, "days", "каждые 2 дня"),
            (5, "days", "каждые 5 дней"),
            (21, "days", "каждый 21 день"),
            (22, "days", "каждые 22 дня"),
            (25, "days", "каждые 25 дней"),
        ],
    )
    def test_get_interval_russian_translation(self, every, period, expected):
        task = PeriodicTaskFactory(interval=IntervalScheduleFactory(every=every, period=period))
        result = get_interval_russian_translation(task)
        assert result == expected


class TestUpdateUserQuotaForScheduledUpdates:
    def test_exception_raised_if_no_quota(self):
        """Exception is raised if user has no quota left"""
        test_user = UserFactory(is_demo_user=True)
        user_quota = test_user.user_quotas.get(user=test_user)
        user_quota.scheduled_updates = 0
        user_quota.save()

        assert user_quota.scheduled_updates == 0
        with pytest.raises(QuotaExceededException):
            update_user_quota_for_scheduled_updates(test_user)
        assert user_quota.scheduled_updates == 0

    def test_exception_not_raised_if_quota(self):
        user = UserFactory(is_demo_user=True)
        user_quota = user.user_quotas.get(user=user)
        user_quota.scheduled_updates = 1
        user_quota.save()

        assert user_quota.scheduled_updates == 1
        update_user_quota_for_scheduled_updates(user)
        user_quota.refresh_from_db()
        assert user_quota.scheduled_updates == 0
