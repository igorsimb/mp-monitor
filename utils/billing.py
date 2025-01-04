"""Billing and quota management utilities."""

import logging
import re
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import HttpRequest

import config
from accounts.models import TenantQuota, Tenant
from main.exceptions import QuotaExceededException
from main.models import Order

logger = logging.getLogger(__name__)
User = get_user_model()


def get_user_quota(user: User) -> TenantQuota | None:
    """Get the user quota for a given user.

    Args:
        user (User): The user for which to get the quota.

    Returns:
        TenantQuota: The user quota for the given user.

    You can access the user quota fields like this:
        user_quota.user_lifetime_hours

        user_quota.max_allowed_skus

        user_quota.manual_updates

        user_quota.scheduled_updates
    """
    try:
        user_quota = user.tenant.quota
    except TenantQuota.DoesNotExist:
        user_quota = None

    return user_quota


def set_tenant_quota(
    tenant: Tenant,
    name: str = "DEMO_QUOTA",
    total_hours_allowed: int = config.DEMO_USER_HOURS_ALLOWED,
    skus_limit: int = config.DEMO_USER_MAX_ALLOWED_SKUS,
    parse_units_limit: int = config.DEMO_USER_ALLOWED_PARSE_UNITS,
) -> None:
    """Set the user quota for a given user."""
    tenant.quota, _ = TenantQuota.objects.get_or_create(
        name=name,
        total_hours_allowed=total_hours_allowed,
        skus_limit=skus_limit,
        parse_units_limit=parse_units_limit,
    )
    # assign the quota to the tenant
    tenant.save(update_fields=["quota"])


def update_tenant_quota_for_max_allowed_sku(request: HttpRequest, skus: str) -> None:
    """
    Checks if the user has enough quota to scrape items and then updates the remaining user quota.

    Args:
        request: The HttpRequest object containing user and form data.
        skus (str): The string of SKUs to check.
    """
    user_quota = get_user_quota(request.user)
    skus_count: int = len(re.split(r"\s+|\n|,(?:\s*)", skus))
    if skus_count <= user_quota.skus_limit:
        user_quota.skus_limit -= skus_count
        user_quota.save()
    else:
        raise QuotaExceededException(
            message="Превышен лимит количества товаров для данного тарифа.",
            quota_type="max_allowed_skus",
        )


def update_user_quota_for_allowed_parse_units(user: User, skus: str) -> None:
    user_quota = get_user_quota(user)
    skus_count = len(re.split(r"\s+|\n|,(?:\s*)", skus))
    if user_quota.parse_units_limit >= skus_count:
        user_quota.parse_units_limit -= skus_count
        user_quota.save()
    else:
        raise QuotaExceededException(
            message="Превышен лимит единиц проверки для данного тарифа.",
            quota_type="allowed_parse_units",
        )


def create_unique_order_id() -> str:
    """Create a unique order ID.

    Returns:
        str: A unique order ID.

    Raises:
        ValidationError: If unable to generate a unique ID after multiple attempts.
    """
    max_attempts = 10
    attempt = 0

    while attempt < max_attempts:
        order_id = str(uuid4())
        if not Order.objects.filter(order_id=order_id).exists():
            return order_id
        attempt += 1

    raise ValidationError("Unable to generate a unique order ID")
