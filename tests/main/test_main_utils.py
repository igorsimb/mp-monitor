import logging

import httpx
import pytest
from django.contrib.auth import get_user_model

from main.models import Item, Tenant
from main.utils import uncheck_all_boxes, scrape_item

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
            Item.objects.create(tenant=tenant, name=f"Item {i}", sku=f"1234{i}", parser_active=True)
            for i in range(1, number_of_items + 1)
        ]

        request.user = user
        logger.info("Calling uncheck_all_boxes() for tenant '%s'", tenant)
        uncheck_all_boxes(request)

        logger.info("Checking that all items for tenant '%s' are updated with parser_active=False", tenant)
        for item in items:
            item.refresh_from_db()
            logger.debug("'%s' parser_active=%s", item.name, item.parser_active)
            assert not item.parser_active

    def test_no_items_exist(self, request, user, tenant):
        """
        Test if uncheck_all_boxes handles the case when no items exist for the user's tenant
        """
        request.user = user
        logger.info("Calling uncheck_all_boxes() with no items")
        uncheck_all_boxes(request)

        assert Item.objects.filter(tenant=tenant).count() == 0

    def test_uncheck_for_one_tenant_when_multiple_tenants_exist(self, request):
        """
        Multiple tenants exist, but only items for the user's tenant are updated
        """
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
        item1 = Item.objects.create(tenant=tenant1, name="Item 1", sku="12345", parser_active=True)
        logger.debug("Item '%s' created", item1)
        item2 = Item.objects.create(tenant=tenant2, name="Item 2", sku="67899", parser_active=True)
        logger.debug("Item '%s' created", item2)

        logger.info("Calling uncheck_all_boxes() for tenant '%s'", tenant1)
        request.user = user1
        uncheck_all_boxes(request)

        logger.info("Checking that only item1 for tenant '%s' is updated with parser_active=False", tenant1)
        item1.refresh_from_db()
        item2.refresh_from_db()
        assert not item1.parser_active, f"Item1 parser_active should be False but it is {item1.parser_active}"
        assert item2.parser_active, f"Item2 parser_active should be True but it is {item2.parser_active}"

    def test_no_items_updated_if_user_not_authenticated(self, request):
        with pytest.raises(AttributeError):
            logger.info("Expecting %s when calling uncheck_all_boxes() without authentication", AttributeError)
            uncheck_all_boxes(request)

        logger.info("Checking that no items are updated")
        assert Item.objects.filter(parser_active=True).count() == 0

    def test_uncheck_all_boxes_already_inactive(self, request, user, tenant):
        """
        Test if the function handles items with parser_active=False gracefully
        """
        Item.objects.create(name="InactiveItem1", tenant=tenant, sku="12345", parser_active=False)
        Item.objects.create(name="InactiveItem2", tenant=tenant, sku="67899", parser_active=False)

        request.user = user
        uncheck_all_boxes(request)

        inactive_items = Item.objects.filter(tenant=tenant, parser_active=False)
        for item in inactive_items:
            assert (
                not item.parser_active
            ), f"Item {item.name} parser_active should be False but it is {item.parser_active}"


class TestScrapeItem:
    # Use pytest-mock (mocker) to isolate the tests from API in case API fails or real item's info changes (e.g. price)
    @pytest.fixture(autouse=True)
    def setup(self, mocker):
        self.sku = "12345"
        self.mock_response = httpx.Response(
            200,
            json={
                "data": {
                    "products": [
                        {
                            "name": "Test Item",
                            "id": self.sku,
                            "salePriceU": 10000,
                            "image": "test.jpg",
                            "category": "Test Category",
                            "brand": "Test Brand",
                            "seller_name": "Test Brand",
                            "rating": 4.5,
                            "feedbacks": 10,
                        }
                    ]
                }
            },
        )

        self.mock_response.request = httpx.Request(
            method="GET", url=f"https://card.wb.ru/cards/detail?appType=1&curr=rub&nm={self.sku}"
        )

        mocker.patch("httpx.get", return_value=self.mock_response)

    def test_retrieve_data_from_mock_api(self):
        logger.info("Calling scrape_item() with a mock SKU (%s)", self.sku)
        result = scrape_item(self.sku)

        logger.info("Checking that the result is the expected parsed item dictionary")
        assert result == {
            "name": "Test Item",
            "sku": self.sku,
            "price": 100.0,
            "image": "test.jpg",
            "category": "Test Category",
            "brand": "Test Brand",
            "seller_name": "Test Brand",
            "rating": 4.5,
            "num_reviews": 10,
        }

    def test_retry_request_on_http_error(self, mocker):
        mocker.patch("httpx.get", side_effect=[
            httpx.HTTPError(message="Expected Error"),
            httpx.HTTPError(message="Expected Error"),
            self.mock_response
        ])

        logger.info("Calling scrape_item() with a mock SKU (%s)", self.sku)
        result = scrape_item(self.sku)

        logger.info("Checking that the result is the expected parsed item dictionary")
        assert result == {
            "name": "Test Item",
            "sku": self.sku,
            "price": 100,
            "image": "test.jpg",
            "category": "Test Category",
            "brand": "Test Brand",
            "seller_name": "Test Brand",
            "rating": 4.5,
            "num_reviews": 10,
        }

    def test_return_none_for_missing_price(self):
        response_data = self.mock_response.json()

        logger.info("Removing the salePriceU field")
        del response_data["data"]["products"][0]["salePriceU"]

        logger.info("Returning the modified response_data dictionary")
        self.mock_response.json = lambda: response_data

        logger.info("Calling scrape_item() with a mock SKU (%s)", self.sku)
        result = scrape_item(self.sku)

        logger.info("Checking that the resulting price is None")
        assert result["price"] is None

    def test_return_none_for_invalid_price_format(self):
        response_data = self.mock_response.json()

        logger.info("Assigning invalid price format to the salePriceU field")
        response_data["data"]["products"][0]["salePriceU"] = "invalidprice"

        logger.info("Returning the modified response_data dictionary")
        self.mock_response.json = lambda: response_data

        logger.info("Calling scrape_item() with a mock SKU (%s)", self.sku)
        result = scrape_item(self.sku)

        logger.info("Checking that the resulting price is None")
        assert result["price"] is None
