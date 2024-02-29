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
from tests.factories import UserFactory, TenantFactory

logger = logging.getLogger(__name__)


User = get_user_model()


class TestTenantModel:
    def test_default_status(self) -> None:
        # Tenant is created on User's save() method
        user = UserFactory()

        assert user.tenant is not None
        assert user.tenant.status == user.tenant.Status.TRIALING

    def test_active_tenant(self) -> None:
        """Tests the active() manager method to ensure it correctly returns active tenants."""
        trialing = TenantFactory(
            status=Tenant.Status.TRIALING, name="unique1@testing.com"
        )
        active = TenantFactory(status=Tenant.Status.ACTIVE, name="unique2@testing.com")
        exempt = TenantFactory(status=Tenant.Status.EXEMPT, name="unique3@testing.com")
        TenantFactory(status=Tenant.Status.CANCELED, name="unique4@testing.com")
        TenantFactory(status=Tenant.Status.TRIAL_EXPIRED, name="unique6@testing.com")

        active_tenants = Tenant.objects.active()  # Queryset, aka a set
        assert set(active_tenants) == {trialing, active, exempt}

    def test_tenant_name_is_equal_to_user_email(self) -> None:
        user = UserFactory()

        assert user.tenant.name == user.email

    def test_create_new_tenant_with_unique_name(self) -> None:
        tenant = Tenant(name="Tenant1")
        tenant.save()
        assert Tenant.objects.filter(name="Tenant1").exists()

    def test_create_new_tenant_with_non_unique_name(self) -> None:
        tenant1 = Tenant(name="Tenant1")
        tenant1.save()
        logger.info(
            "Creating a new Tenant with the same name as the previous one: %s", tenant1
        )
        tenant2 = Tenant(name="Tenant1")
        logger.info("Checking that new Tenant is not saved")
        with pytest.raises(IntegrityError):
            tenant2.save()

    def test_create_new_tenant_with_empty_name(self) -> None:
        tenant = Tenant(name="")
        logger.info("Checking that a tenant with an empty name cannot be saved...")
        with pytest.raises(IntegrityError):
            tenant.save()

    def test_retrieve_existing_tenant_by_name(self) -> None:
        tenant = Tenant(name="Tenant1")
        tenant.save()
        retrieved_tenant = Tenant.objects.get(name="Tenant1")
        assert retrieved_tenant == tenant

    def test_update_existing_tenant_name(self) -> None:
        tenant = Tenant(name="Tenant1")
        tenant.save()
        tenant.name = "Tenant2"
        tenant.save()
        updated_tenant = Tenant.objects.get(name="Tenant2")
        assert updated_tenant == tenant

    def test_retrieve_non_existing_tenant(self) -> None:
        with pytest.raises(ObjectDoesNotExist):
            logger.info("Raising the following exception:  %s", ObjectDoesNotExist)
            Tenant.objects.get(name="NonExistingTenant")

    def test_delete_existing_tenant(self) -> None:
        tenant = Tenant.objects.create(name="Test Tenant")
        logger.info("Deleting the tenant '%s'...", tenant)
        tenant.delete()

        logger.info(
            "Checking that the tenant '%s' is no longer in the database...", tenant
        )
        with pytest.raises(ObjectDoesNotExist):
            Tenant.objects.get(name="Test Tenant")


class TestItemModel:
    def test_create_item(self) -> None:
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

    def test_duplicate_sku(self) -> None:
        logger.info(
            "Checking that UNIQUE constraint for main_item.tenant_id, main_item.sku fails as expected"
        )
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

    def test_get_absolute_url(self) -> None:
        item = Item.objects.create(
            tenant_id=1,
            name="Sample Item",
            sku="12345",
            price=100,
        )
        assert item.get_absolute_url() == reverse(
            "item_detail", kwargs={"slug": "12345"}
        )

    def test_str_method(self) -> None:
        item = Item.objects.create(
            tenant_id=1,
            name="Sample Item",
            sku="12345",
            price=100,
        )
        assert str(item) == "Sample Item (12345)"

    def test_save_method_creates_price(self) -> None:
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
    def item_group(self) -> Group:
        group = Group.objects.create(name="Test Group")
        return group

    @pytest.fixture
    def tenant(self) -> Tenant:
        tenant = Tenant.objects.create(name="Test Group")
        return tenant

    def test_creating_item_adds_view_item_permission(
        self, item_group: Group, tenant: Tenant
    ) -> None:
        item = Item.objects.create(
            tenant=tenant,
            name="Sample Item",
            sku="12345",
            price=100,
        )
        logger.info(
            "Checking if the 'view_item' permission is assigned to the group '%s'",
            item_group.name,
        )
        assert (
            "view_item" in get_perms(item_group, item)
        ), f"Expected 'view_item' permission to be assigned to the group '{item_group.name}' but it wasn't"

    def test_manual_add_perm_does_not_create_duplicate_perm(
        self, item_group: Group, tenant: Tenant
    ) -> None:
        item = Item.objects.create(
            tenant=tenant,
            name="Sample Item",
            sku="12345",
            price=100,
        )

        logger.info(
            "Manually adding the 'view_item' permission for item '%s' to group '%s'",
            item.name,
            item_group,
        )
        assign_perm("main.view_item", item_group, item)

        logger.info(
            "Checking that the signal does not add a duplicate permission to group"
        )
        assert (
            len(get_perms(item_group, item)) == 1
        ), f"Group '{item_group}' should have only 1 permission, but it has {len(get_perms(item_group, item))}"


class TestPriceModel:
    @pytest.fixture
    def tenant(self) -> Tenant:
        return Tenant.objects.create(name="Test Organization")

    @pytest.fixture
    def item(self, tenant: Tenant) -> Item:
        return Item.objects.create(
            tenant=tenant,
            name="Test Item",
            sku="SKU123",
            price=100,
        )

    def test_create_price(self, item: Item) -> None:
        price = Price.objects.create(item=item, value=99)
        logger.info("Checking if the Price instance was created successfully...")
        assert price.id is not None

    def test_create_new_price_with_valid_parameters(self, item: Item) -> None:
        price = Price.objects.create(item=item, value=10, created_at=timezone.now())
        assert price.value == 10

    def test_retrieve_price_created_at(self, item: Item) -> None:
        current_time = timezone.now()
        price = Price.objects.create(item=item, value=10, created_at=current_time)

        # Truncate both datetime values to the minute, no need for (milli)seconds
        price_created_at_minutes = price.created_at.replace(microsecond=0)
        current_time_minutes = current_time.replace(microsecond=0)

        assert price_created_at_minutes == current_time_minutes

    def test_create_new_price_with_null_value(self, item: Item) -> None:
        price = Price.objects.create(item=item, value=None, created_at=timezone.now())

        assert price.value is None

    def test_create_new_price_with_negative_value(self, item: Item) -> None:
        with pytest.raises(IntegrityError):
            logger.info(
                "Checking that a new Price object with a negative value cannot be saved due to "
                "no_negative_price_value CHECK constraint..."
            )
            Price.objects.create(item=item, value=-100, created_at=timezone.now())
