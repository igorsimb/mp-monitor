import logging

import httpx
import pytest
from django.contrib.auth import get_user_model

from accounts.models import Tenant
from main.models import Item
from main.tasks import scrape_interval_task

logger = logging.getLogger(__name__)

User = get_user_model()


class TestScrapeIntervalTask:
    # pylint: disable=[no-value-for-parameter]
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
                "basicSale": 30,
                "sale": 30,
                "image": "test1.jpg",
                "category": "Test Category 1",
                "brand": "Test Brand 1",
                "seller_name": "Test Brand 1",
                "rating": 4.5,
                "feedbacks": 10,
                "extended": {
                    "basicPriceU": "salePriceU",
                    "basicSale": "basicSale",
                },
                "sizes": [{"stocks": ["3"], "price": {"basic": 10000, "total": 10000}}],
            },
            self.sku2: {
                "name": self.name2,
                "salePriceU": 15000,
                "basicSale": 30,
                "sale": 30,
                "image": "test2.jpg",
                "category": "Test Category 2",
                "brand": "Test Brand 2",
                "seller_name": "Test Brand 2",
                "rating": 4.2,
                "feedbacks": 8,
                "extended": {
                    "basicPriceU": "salePriceU",
                    "basicSale": "basicSale",
                },
                "sizes": [{"stocks": ["3"], "price": {"basic": 15000, "total": 15000}}],
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
                                "priceU": data["salePriceU"],
                                "sale": data["sale"],
                                "image": data["image"],
                                "category": data["category"],
                                "brand": data["brand"],
                                "seller_name": data["seller_name"],
                                "rating": data["rating"],
                                "feedbacks": data["feedbacks"],
                                "live_price": data["salePriceU"],
                                "extended": {
                                    "basicPriceU": data["salePriceU"],
                                    "sale": data["basicSale"],
                                },
                                "sizes": [
                                    {
                                        "stocks": ["3"],
                                        "price": {"basic": data["salePriceU"], "total": data["salePriceU"]},
                                    }
                                ],
                            }
                        ]
                    },
                },
            )
            logger.debug("Item created with SKU=%s", sku)

            mock_response.request = httpx.Request(
                method="GET",
                url=f"https://card.wb.ru/cards/v2/detail?appType=1&curr=rub&nm={sku}",
            )

            mock_responses.append(mock_response)

        mocker.patch("httpx.get", side_effect=mock_responses)

    @pytest.fixture
    def user(self) -> User:
        return User.objects.create_user(username="testuser", email="testuser@test.com", password="testpassword")

    @pytest.fixture
    def tenant(self, user: User) -> Tenant:
        return Tenant.objects.get(name__startswith=user.email)

    @pytest.fixture
    def items(self, tenant: Tenant) -> list:
        item1 = Item.objects.create(sku=self.sku1, name=self.name1, tenant=tenant)
        item2 = Item.objects.create(sku=self.sku2, name=self.name2, tenant=tenant)
        return [item1, item2]

    def test_scrape_interval_task_updates_item_price(self, items: list, tenant: Tenant, mocker) -> None:
        item1_old_price = items[0].price
        item2_old_price = items[1].price

        logger.info("Checking that %s's Price before running task is None", items[0].name)
        assert items[0].price is None, f"{items[0].name}'s price should be None, but it is {item1_old_price}"
        logger.info("Checking that %s's Price before running task is None", items[1].name)
        assert items[1].price is None, f"{items[1].name}'s price should be None, but it is {item2_old_price}"

        # scrape_live_price uses selenium to get the live price of the item from WB
        # So mocking is necessary to avoid going to WB
        mocker.patch("utils.marketplace.scrape_live_price", return_value=100)
        scrape_interval_task(tenant.id, selected_item_ids=[items[0].id])

        mocker.patch("utils.marketplace.scrape_live_price", return_value=150)
        scrape_interval_task(tenant.id, selected_item_ids=[items[1].id])

        items[0].refresh_from_db()
        items[1].refresh_from_db()
        item1_new_price = items[0].price
        item2_new_price = items[1].price

        logger.debug("Item1 Price after running task: %s", item1_new_price)
        logger.debug("Item2 Price after running task: %s", item2_new_price)

        assert item1_old_price != item1_new_price
        assert item2_old_price != item2_new_price

        assert items[0].name == self.name1
        logger.info(
            "Checking that %s's Price after running task was updated correctly",
            items[0].name,
        )
        assert items[0].price == 100

        # mocker.patch("main.utils.scrape_live_price", return_value=150)
        assert items[1].name == self.name2
        logger.info(
            "Checking that %s's Price after running task was updated correctly",
            items[1].name,
        )
        assert items[1].price == 150

    def test_no_items_created_if_no_id(self, tenant: Tenant) -> None:
        scrape_interval_task(tenant.id, selected_item_ids=[])

        logger.debug("Items: %s", Item.objects.all())
        assert Item.objects.all().count() == 0

    def test_no_items_created_if_invalid_id(self, tenant: Tenant, mocker) -> None:  # type: ignore
        invalid_items_ids = [998, 999]

        logger.info("Mocking the 'Item.objects.filter' method to return an empty list")
        mocker.patch("main.tasks.Item.objects.filter", return_value=[])

        logger.info(
            "Calling the 'scrape_interval_task' function with with invalid item ids: %s",
            invalid_items_ids,
        )
        scrape_interval_task(tenant.id, selected_item_ids=invalid_items_ids)

        logger.debug("Items: %s", Item.objects.all())
        assert Item.objects.all().count() == 0

        logger.info(
            "Checking that the Item.objects.filter method was called with the correct arguments: ids=%s",
            invalid_items_ids,
        )
        Item.objects.filter.assert_called_once_with(id__in=invalid_items_ids)  # type: ignore

    def test_invalid_tenant_id_is_called(self, items: list, mocker) -> None:  # type: ignore
        invalid_tenant_id = 999

        logger.info("Mocking the 'Tenant.objects.get' method to raise an exception")
        mocker.patch("main.tasks.Tenant.objects.get", side_effect=Tenant.DoesNotExist)

        logger.info(
            "Calling the 'scrape_interval_task' function with an invalid tenant id (%s)",
            invalid_tenant_id,
        )
        with pytest.raises(Tenant.DoesNotExist):
            scrape_interval_task(
                tenant_id=invalid_tenant_id,
                selected_item_ids=[item.id for item in items],
            )

        logger.info(
            "Checking that the 'Tenant.objects.get' method was called once with the correct arguments (id=%s),",
            invalid_tenant_id,
        )
        Tenant.objects.get.assert_called_once_with(id=invalid_tenant_id)  # type: ignore
