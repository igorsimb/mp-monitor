import logging

import pytest

from accounts.models import Tenant
from factories import ItemFactory, UserFactory
from utils import items

logger = logging.getLogger(__name__)


class TestGetItemsWithPriceChangesOverThreshold:
    @pytest.fixture
    def tenant(self) -> Tenant:
        user = UserFactory()
        user.is_superuser = True  # TODO: remove this once it is removed from the function
        user.save()
        return user.tenant

    def test_item_with_price_change(self, tenant: Tenant) -> None:
        logger.info("Setting tenant's threshold to 0.1...")
        tenant.price_change_threshold = 0.1

        item = ItemFactory(tenant=tenant)
        item.is_notifier_active = True

        logger.info("Creating item_data...")
        item_data = {
            "name": item.name,
            "sku": item.sku,
            "is_notifier_active": item.is_notifier_active,
        }

        logger.info("Updating item price...")
        item.price -= 10
        item.save()
        item.refresh_from_db()

        items_with_price_change = items.get_items_with_price_changes_over_threshold(tenant, [item_data])
        logger.info("Checking if the item with price change is in the list...")
        assert len(items_with_price_change) == 1

    def test_item_with_no_price_change(self, tenant: Tenant) -> None:
        logger.info("Setting tenant's threshold to 0.1...")
        tenant.price_change_threshold = 0.1

        item = ItemFactory(tenant=tenant)
        item.is_notifier_active = True

        logger.info("Creating item_data...")
        item_data = {
            "name": item.name,
            "sku": item.sku,
            "is_notifier_active": item.is_notifier_active,
        }

        items_with_price_change = items.get_items_with_price_changes_over_threshold(tenant, [item_data])
        logger.info("Checking that the item is not in the list...")
        assert len(items_with_price_change) == 0
