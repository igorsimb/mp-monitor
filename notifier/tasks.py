import logging

from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from accounts.models import Tenant

logger = logging.getLogger(__name__)


@shared_task
def send_price_change_email(tenant_id: int, items_data: list[dict]) -> None:
    """
    Send an email notification to all users of a tenant about the price change of their items.

    Args:
        tenant_id (int): The ID of the tenant.
        items_data (list): A list of dictionaries containing the data for the items that have changed their prices.
    """
    tenant = Tenant.objects.get(id=tenant_id)
    user = tenant.users.first()
    email_subject = f"Цена товаров ({len(items_data)}) изменилась"
    email_recipients = [user.email for user in tenant.users.all()]

    text_content = render_to_string(
        "notifier/emails/price_change_notification.txt", context={"user": user.profile.name, "items": items_data}
    )

    html_content = render_to_string(
        "notifier/emails/price_change_notification.html", context={"user": user.profile.name, "items": items_data}
    )

    logger.info(f"Sending email to {email_recipients} with subject '{email_subject}'")
    msg = EmailMultiAlternatives(
        email_subject,
        text_content,
        "info@mpmonitor.ru",
        email_recipients,
    )

    msg.attach_alternative(html_content, "text/html")
    msg.send()
