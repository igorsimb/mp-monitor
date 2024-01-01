import logging

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from guardian.shortcuts import assign_perm, get_perms

from main.models import Tenant, Item, Price

logger = logging.getLogger(__name__)

pytestmark = [pytest.mark.django_db]

User = get_user_model()


class TestTenantModel:
    def test_create_new_tenant_with_unique_name(self):
        tenant = Tenant(name="Tenant1")
        tenant.save()
        assert Tenant.objects.filter(name="Tenant1").exists()

    def test_create_new_tenant_with_non_unique_name(self):
        tenant1 = Tenant(name="Tenant1")
        tenant1.save()
        logger.info("Creating a new Tenant with the same name as the previous one: %s", tenant1)
        tenant2 = Tenant(name="Tenant1")
        logger.info("Checking that new Tenant is not saved")
        with pytest.raises(IntegrityError):
            tenant2.save()

    def test_create_new_tenant_with_empty_name(self):
        tenant = Tenant(name="")
        logger.info("Checking that a tenant with an empty name cannot be saved...")
        with pytest.raises(IntegrityError):
            tenant.save()

    def test_retrieve_existing_tenant_by_name(self):
        tenant = Tenant(name="Tenant1")
        tenant.save()
        retrieved_tenant = Tenant.objects.get(name="Tenant1")
        assert retrieved_tenant == tenant

    def test_update_existing_tenant_name(self):
        tenant = Tenant(name="Tenant1")
        tenant.save()
        tenant.name = "Tenant2"
        tenant.save()
        updated_tenant = Tenant.objects.get(name="Tenant2")
        assert updated_tenant == tenant

    def test_retrieve_non_existing_tenant(self):
        with pytest.raises(ObjectDoesNotExist):
            logger.info("Raising the following exception:  %s", ObjectDoesNotExist)
            Tenant.objects.get(name="NonExistingTenant")

    def test_delete_existing_tenant(self):
        tenant = Tenant.objects.create(name="Test Tenant")
        logger.info("Deleting the tenant '%s'...", tenant)
        tenant.delete()

        logger.info("Checking that the tenant '%s' is no longer in the database...", tenant)
        with pytest.raises(ObjectDoesNotExist):
            Tenant.objects.get(name="Test Tenant")


class TestItemModel:
    def test_create_item(self):
        item = Item.objects.create(
            tenant_id=1,
            name="Sample Item",
            sku="12345",
            price=100,
            image="https://example.com/sample.jpg",
            category="Sample Category",
            brand="Sample Brand",
            seller_name="Sample Seller",
            rating=4.5,
            num_reviews=50,
            is_parser_active=True,
        )
        assert item.pk is not None

    def test_duplicate_sku(self):
        logger.info("Checking that UNIQUE constraint for main_item.tenant_id, main_item.sku fails as expected")
        with pytest.raises(IntegrityError):
            Item.objects.create(
                tenant_id=1,
                name="Sample Item",
                sku="12345",
                price=100,
            )
            Item.objects.create(
                tenant_id=1,
                name="Another Item",
                sku="12345",
                price=200,
            )

    def test_get_absolute_url(self):
        item = Item.objects.create(
            tenant_id=1,
            name="Sample Item",
            sku="12345",
            price=100,
        )
        assert item.get_absolute_url() == reverse("item_detail", kwargs={"slug": "12345"})

    def test_str_method(self):
        item = Item.objects.create(
            tenant_id=1,
            name="Sample Item",
            sku="12345",
            price=100,
        )
        assert str(item) == "Sample Item (12345)"

    def test_save_method_creates_price(self):
        """Whenever Item object is saved, a new Price object should be created."""
        item = Item.objects.create(
            tenant_id=1,
            name="Sample Item",
            sku="12345",
            price=100,
        )
        assert Price.objects.filter(item=item).count() == 1


class TestAddPermsToGroupSignal:
    @pytest.fixture
    def item_group(self):
        group = Group.objects.create(name="Test Group")
        return group

    @pytest.fixture
    def tenant(self):
        tenant = Tenant.objects.create(name="Test Group")
        return tenant

    def test_creating_item_adds_view_item_permission(self, item_group, tenant):
        item = Item.objects.create(
            tenant=tenant,
            name="Sample Item",
            sku="12345",
            price=100,
        )
        logger.info("Checking if the 'view_item' permission is assigned to the group '%s'", item_group.name)
        assert "view_item" in get_perms(
            item_group, item
        ), f"Expected 'view_item' permission to be assigned to the group '{item_group.name}' but it wasn't"

    def test_manual_add_perm_does_not_create_duplicate_perm(self, item_group, tenant):
        item = Item.objects.create(
            tenant=tenant,
            name="Sample Item",
            sku="12345",
            price=100,
        )

        logger.info("Manually adding the 'view_item' permission for item '%s' to group '%s'", item.name, item_group)
        assign_perm("main.view_item", item_group, item)

        logger.info("Checking that the signal does not add a duplicate permission to group")
        assert (
            len(get_perms(item_group, item)) == 1
        ), f"Group '{item_group}' should have only 1 permission, but it has {len(get_perms(item_group, item))}"


class TestPriceModel:
    @pytest.fixture
    def tenant(self):
        return Tenant.objects.create(name="Test Organization")

    @pytest.fixture
    def item(self, tenant):
        return Item.objects.create(
            tenant=tenant,
            name="Test Item",
            sku="SKU123",
            price=100,
        )

    def test_create_price(self, item):
        price = Price.objects.create(item=item, value=99)
        logger.info("Checking if the Price instance was created successfully...")
        assert price.id is not None

    def test_create_new_price_with_valid_parameters(self, item):
        price = Price.objects.create(item=item, value=10, created_at=timezone.now())
        assert price.value == 10

    def test_retrieve_price_created_at(self, item):
        current_time = timezone.now()
        price = Price.objects.create(item=item, value=10, created_at=current_time)

        # Truncate both datetime values to the minute, no need for (milli)seconds
        price_created_at_minutes = price.created_at.replace(microsecond=0)
        current_time_minutes = current_time.replace(microsecond=0)

        assert price_created_at_minutes == current_time_minutes

    def test_create_new_price_with_null_value(self, item):
        price = Price.objects.create(item=item, value=None, created_at=timezone.now())

        assert price.value is None

    def test_create_new_price_with_negative_value(self, item):
        with pytest.raises(IntegrityError):
            logger.info(
                "Checking that a new Price object with a negative value cannot be saved due to "
                "no_negative_price_value CHECK constraint..."
            )
            Price.objects.create(item=item, value=-100, created_at=timezone.now())
