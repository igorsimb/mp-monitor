import logging
from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

from accounts.models import Tenant

logger = logging.getLogger(__name__)


@shared_task
def send_price_change_email(tenant_id, items_data):
    """
    Send an email notification to all users of a tenant about the price change of their items.

    Args:
        tenant_id (int): The ID of the tenant.
        items_data (list): A list of dictionaries containing the data for the items that have changed their prices.
    """
    tenant = Tenant.objects.get(id=tenant_id)
    email_subject = "Цена товаров изменилась"
    email_recipients = [user.email for user in tenant.users.all()]

    # Prepare email content using a template
    email_content = render_to_string(
        "notifier/emails/price_change_notification.html", {"tenant": tenant, "items": items_data}
    )
    logger.info(f"Sending email to {email_recipients} with subject '{email_subject}'")
    send_mail(
        subject=email_subject,
        message="",
        from_email="info@mpmonitor.ru",
        recipient_list=email_recipients,
        html_message=email_content,
    )
