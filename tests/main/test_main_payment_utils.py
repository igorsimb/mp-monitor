import pytest
from django.utils import timezone

from factories import TenantFactory, PaymentPlanFactory
from main.models import Order
from utils.payment import update_payment_records


class TestUpdatePaymentRecords:
    order_id = "234468"
    payment_id = "5193492412"

    @pytest.fixture
    def payment_data(self):
        return {
            "OrderId": self.order_id,
            "PaymentId": self.payment_id,
            "Amount": 1199000,
        }

    @pytest.fixture
    def tenant(self):
        return TenantFactory()

    @pytest.fixture
    def plan(self):
        return PaymentPlanFactory()

    @pytest.fixture
    def order(self, tenant, plan):
        order = Order.objects.create(
            tenant=tenant,
            order_id=self.order_id,
            amount=plan.price,
            description=plan.name,
            status=Order.OrderStatus.PENDING,
            order_intent=Order.OrderIntent.ADD_TO_BALANCE,
            created_at=timezone.now(),
        )
        return order

    def test_order_exists(self, order: Order) -> None:
        assert order is not None

    def test_order_status_updated(self, payment_data: dict, order: Order) -> None:
        update_payment_records(payment_data, order)

        order.refresh_from_db()
        assert order.status == Order.OrderStatus.PAID

    def test_incorrect_payment_records_not_updated(self, payment_data, order):
        """Test that incorrect payment data does not update records."""
        # TODO: check this test
        # Modify data to simulate incorrect callback
        # data["Amount"] = 999999  # Invalid amount
        #
        # # Run function and verify no Payment is created
        # update_payment_records(data, order)
        #
        # # Assert that no successful Payment record exists
        # assert not Payment.objects.filter(order=order, is_successful=True).exists()
        #
        # # Assert order status is not set to PAID
        # order.refresh_from_db()
        # assert order.status == Order.OrderStatus.PENDING
        pass

    # TODO: add tests for the following functions:
    # 1. Order
    # 2. Payment
    # 3. Tenant

    # Assert Payment record is created and linked to the tenant and order
    # payment = Payment.objects.get(order=order)
    # assert payment.is_successful is True
    # assert payment.amount == data["Amount"] / 100  # Converted to rubles
    # assert payment.payment_id == self.payment_id
    # assert payment.tenant == order.tenant

    # test balance is updated and plan not switched if order intent is ADD_TO_BALANCE
    # test plan is switched if order intent is SWITCH_PLAN
    # test billing_start_date is updated if order intent is SWITCH_PLAN
