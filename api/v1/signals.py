import logging

from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from main.models import Item

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=Item)
def invalidate_item_cache(sender, instance, **kwargs):
    """
    Invalidate item list caches when an item is created, updated or deleted
    """
    logger.info("Clearing item cache")
    cache.delete_pattern("*item_list*")
