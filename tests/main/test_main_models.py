import logging

import pytest
from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError

from main.models import Tenant

logger = logging.getLogger(__name__)


@pytest.mark.django_db
class TestTenantModel:
    def test_create_new_tenant_with_unique_name(self):
        tenant = Tenant(name="Tenant1")
        tenant.save()
        assert Tenant.objects.filter(name="Tenant1").exists()

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

    def test_create_new_tenant_with_non_unique_name(self):
        tenant1 = Tenant(name="Tenant1")
        tenant1.save()
        logger.info("Creating a new Tenant with the same name as the previous one: %s", tenant1)
        tenant2 = Tenant(name="Tenant1")
        logger.info("Checking that new Tenant is not saved")
        with pytest.raises(IntegrityError):
            tenant2.save()

    #  Create a new Tenant with an empty name
    def test_create_new_tenant_with_empty_name(self):
        tenant = Tenant(name="")
        logger.info("Checking that a tenant with an empty name cannot be saved...")
        with pytest.raises(IntegrityError):
            tenant.save()

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
