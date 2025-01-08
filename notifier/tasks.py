import logging

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from accounts.models import Tenant
from main.models import Item

logger = logging.getLogger(__name__)


@shared_task
def _send_price_change_email(tenant: Tenant, items: list[Item]) -> None:
    """
    Send an email notification to all users of a tenant about the price change of their items.
    Only sends info about items that have notifier enabled (is_notifier_active=True)

    Args:
        tenant (Tenant): The tenant object.
        items (list): A list of Item objects containing the data for the items that have changed their prices.
    """

    user = tenant.users.first()
    if not items:
        return
    items_with_notifier_active = [item for item in items if item.is_notifier_active]
    if not items_with_notifier_active:
        logger.info("No items have active notifiers. Exiting.")
        return

    email_subject = f"Цена товаров ({len(items_with_notifier_active)}) изменилась"
    email_recipients = [user.email for user in tenant.users.all()]
    logger.info("Found %s items with notifier enabled", len(items_with_notifier_active))

    context = {"user_name": user.profile.name, "items": items_with_notifier_active}

    text_content = render_to_string("notifier/emails/price_change_notification.txt", context)
    html_content = render_to_string("notifier/emails/price_change_notification.html", context)

    logger.info(f"Sending email to {email_recipients} with subject '{email_subject}'")
    msg = EmailMultiAlternatives(
        email_subject,
        text_content,
        "info@mpmonitor.ru",
        email_recipients,
    )

    msg.attach_alternative(html_content, "text/html")
    msg.send()


@shared_task
def send_price_change_email(tenant: Tenant, items: list[Item]) -> None:
    """
    Send an email notification to all users of a tenant about the price change of their items.
    Only sends info about items that have notifier enabled (is_notifier_active=True)

    Args:
        tenant (Tenant): The tenant object.
        items (list): A list of Item objects containing the data for the items that have changed their prices.
    """
    logger.info("Sending price change email to users...")
    user = tenant.users.first()
    if not items:
        logger.info("No items have active notifiers. Exiting.")
        return

    email_subject = f"Цена товаров ({len(items)}) изменилась"
    email_recipients = [user.email for user in tenant.users.all()]

    context = {"user_name": user.profile.name, "items": items}

    text_content = render_to_string("notifier/emails/price_change_notification.txt", context)
    html_content = render_to_string("notifier/emails/price_change_notification.html", context)

    logger.info("Sending email to %s with subject '%s'", email_recipients, email_subject)
    msg = EmailMultiAlternatives(
        email_subject,
        text_content,
        "info@mpmonitor.ru",
        email_recipients,
    )

    msg.attach_alternative(html_content, "text/html")
    msg.send()
    logger.info("Price change email sent successfully")
