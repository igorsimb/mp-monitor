import decimal
import logging

from django.dispatch import receiver, Signal

from main.models import Item, Price
from .tasks import send_price_change_email

logger = logging.getLogger(__name__)

price_updated = Signal()


# @receiver(post_save, sender=Item)
@receiver(price_updated, sender=Item)
def check_price_change(sender, instance, **kwargs):
    """
    Check if the price of an item has changed by more than the threshold
    specified in the tenant settings. If it has, trigger send_price_change_email task.

    WARNING! A separate email is sent for each item if its price has changed. Meaning, it could lead to multiple emails
    being sent in a short period of time.
    """

    # temporary limiting functionality to superusers
    if not instance.tenant.users.filter(is_superuser=True).exists():
        return

    prices = Price.objects.filter(item=instance).order_by("-created_at")[:2]

    if len(prices) <= 1:
        logger.info("Not enough prices to calculate percent change. Skipping price change notification.")
        return

    elif len(prices) == 2:
        current_price = prices[0].value  # Latest price
        previous_price = prices[1].value  # Previous price
        try:
            percent_change = ((current_price - previous_price) / previous_price) * 100
        except decimal.InvalidOperation as e:
            logger.error(
                "Division by zero occurred while calculating percent change. Skipping price change notification. %s", e
            )
            return
        print(f"Previous price: {previous_price}, current price: {current_price}, percent change: {percent_change}")

        threshold = instance.tenant.price_change_threshold or 0.00
        # If the price change exceeds the threshold and is cheaper than the previous price, trigger email task
        if abs(percent_change) >= threshold and current_price < previous_price:
            items_data = [
                {
                    "name": instance.name,
                    "old_price": previous_price,
                    "new_price": current_price,
                    "percent_change": round(percent_change, 2),
                }
            ]
            if instance.is_notifier_active:
                logger.info("Price change notification triggered for item '%s'. Email sent.", instance.name)
                send_price_change_email.delay(instance.tenant.id, items_data)
            else:
                logger.info("Price change notification is disabled for item '%s'. Email not sent.", instance.name)
