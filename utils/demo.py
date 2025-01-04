"""
Demo system management utilities for handling demo users and demo data.
"""

import logging
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from main.models import Item

logger = logging.getLogger(__name__)
User = get_user_model()


def create_demo_user() -> tuple[User, str]:
    """
    Create a demo user with a random name and password.
    """
    name_uuid = str(uuid4())
    password_uuid = str(uuid4())

    try:
        demo_user = User.objects.create(
            username=f"demo-user-{name_uuid}",
            email=f"demo-user-{name_uuid}@demo.com",
            is_demo_user=True,
            is_demo_active=True,
        )
        demo_user.set_password(password_uuid)
        demo_user.save()
    except IntegrityError as e:
        logger.error("Integrity error during demo user creation: %s", e)
        raise
    except ValidationError as e:
        logger.error("Validation error during demo user creation: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error during demo user creation: %s", e)
        raise

    logger.info("Demo user created with email: %s | password: %s", demo_user.email, password_uuid)
    return demo_user, password_uuid


def create_demo_items(demo_user: User) -> list[Item]:
    """Create demo items for the given user."""
    items = [
        {
            "tenant": demo_user.tenant,
            "name": "Таймер кухонный электронный для яиц на магните",
            "sku": "101231520",
            "price": 500,
        },
        {
            "tenant": demo_user.tenant,
            "name": "Гидрофильное гель-масло для умывания и очищения лица",
            "sku": "31299196",
            "price": 500,
        },
    ]

    created_items = []
    try:
        for item in items:
            created_item = Item.objects.create(**item)
            created_items.append(created_item)
    except IntegrityError as e:
        logger.error("Integrity error during demo items creation: %s", e)
        raise
    except ValidationError as e:
        logger.error("Validation error during demo items creation: %s", e)
        raise
    except Exception as e:
        logger.error("Unexpected error during demo items creation: %s", e)
        raise

    return created_items


def no_active_demo_user(user: User) -> bool:
    """Make sure no active demo user exists for the user.
    Prevents the user from going directly to demo/ url and creating another demo session
    while the first one is still active.
    """
    return not (user.is_authenticated and hasattr(user, "is_demo_user") and user.is_demo_user)
