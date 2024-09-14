from django.db.models.signals import post_save
from django.dispatch import receiver

from main.models import Price, Item
from .tasks import send_price_change_email


@receiver(post_save, sender=Item)
def check_price_change(sender, instance, **kwargs):
    """
    Check if the price of an item has changed by more than the threshold
    specified in the tenant settings. If it has, send an email notification.
    """

    prices = Price.objects.filter(item=instance).order_by("created_at")[:2]

    if len(prices) == 2:
        current_price = prices[0].value  # Latest price
        previous_price = prices[1].value  # Previous price
        percent_change = ((current_price - previous_price) / previous_price) * 100

        threshold = instance.tenant.price_change_threshold or 0

        # If the price change exceeds the threshold, trigger the notification
        if abs(percent_change) >= threshold:
            items_data = [
                {
                    "name": instance.name,
                    "old_price": previous_price,
                    "new_price": current_price,
                    "percent_change": round(percent_change, 2),
                }
            ]
            send_price_change_email.delay(instance.tenant.id, items_data)
