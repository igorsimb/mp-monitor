import pytest
from django.core import mail

from accounts.models import Tenant
from factories import UserFactory, ItemFactory
from notifier.tasks import send_price_change_email


class TestSendPriceChangeEmail:
    @pytest.fixture
    def tenant(self) -> Tenant:
        user = UserFactory()
        return user.tenant

    @pytest.fixture
    def items(self) -> list:
        return [
            ItemFactory(is_notifier_active=True),
            ItemFactory(is_notifier_active=False),
        ]

    def test_message_was_sent(self, tenant: Tenant, items: list) -> None:
        """
        Test that the email send was triggered by the task.
        """
        send_price_change_email(tenant, items)

        assert len(mail.outbox) == 1

    def test_email_recipient(self, tenant: Tenant, items: list) -> None:
        send_price_change_email(tenant, items)

        email = mail.outbox[0]
        assert tenant.users.first().email in email.to, "Email recipient is incorrect."

    def test_email_subject(self, tenant: Tenant, items: list) -> None:
        send_price_change_email(tenant, items)

        email = mail.outbox[0]
        assert tenant.users.first().email in email.to, "Email recipient is incorrect."
        assert "Цена товаров" in email.subject, "Email subject is incorrect."

    def test_email_body(self, tenant: Tenant, items: list) -> None:
        send_price_change_email(tenant, items)

        email = mail.outbox[0]
        assert any(
            item.name in email.body for item in items if item.is_notifier_active
        ), "Email body should contain names of items with notifier enabled."

    def test_email_alternative_is_attached(self, tenant: Tenant, items: list) -> None:
        send_price_change_email(tenant, items)

        email = mail.outbox[0]
        assert email.alternatives[0][1] == "text/html", "Email HTML alternative not attached."

    def test_no_items(self, tenant: Tenant) -> None:
        send_price_change_email(tenant, [])

        assert len(mail.outbox) == 0

    def test_no_active_notifiers(self, tenant: Tenant, items: list) -> None:
        items[0].is_notifier_active = False
        items[0].save()

        send_price_change_email(tenant, items)

        assert len(mail.outbox) == 0
