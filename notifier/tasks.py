from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string

from accounts.models import Tenant


@shared_task
def send_price_change_email(tenant_id, items_data):
    tenant = Tenant.objects.get(id=tenant_id)
    email_subject = "Цена товаров изменилась"
    email_recipients = [user.email for user in tenant.users.all()]

    # Prepare email content using a template
    email_content = render_to_string(
        "notifier/emails/price_change_notification.html", {"tenant": tenant, "items": items_data}
    )

    send_mail(
        subject=email_subject,
        message="",
        from_email="no-reply@mpmonitor.ru",
        recipient_list=email_recipients,
        html_message=email_content,
    )
