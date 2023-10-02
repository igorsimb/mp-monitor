import logging

import pytest
from django.contrib.auth import get_user_model

from main.models import Item, Tenant
from main.utils import uncheck_all_boxes

logger = logging.getLogger(__name__)

User = get_user_model()


@pytest.mark.django_db
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
        items = [Item.objects.create(tenant=tenant, name=f"Item {i}", sku=f"1234{i}", parser_active=True)
                 for i in range(1, number_of_items + 1)]

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
            assert not item.parser_active, \
                f"Item {item.name} parser_active should be False but it is {item.parser_active}"
