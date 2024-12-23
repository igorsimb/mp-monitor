import hashlib
import hmac

import logging
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from main.models import Order, Payment
from mp_monitor import settings

logger = logging.getLogger(__name__)


def validate_callback_data(data: dict, order: Order) -> tuple[bool, str | None]:
    """
    Validates the incoming callback data from the payment provider.

    Args:
        data (dict): The callback data received from the payment provider.
        order (Order): The order object to validate against.
    Returns:
        tuple[bool, str | None]: A tuple where the first value is a boolean
                                    indicating success or failure, and the second
                                    value is an optional error message.
    """

    logger.info("Validating the callback following data...")

    logger.debug("Checking payment status...")
    if data.get("Status") != "CONFIRMED":
        return (
            False,
            f'Invalid payment status, received: {data.get("Status")}. Only "CONFIRMED" is status is processed.',
        )

    logger.debug("Checking terminal key...")
    if data.get("TerminalKey") != settings.TINKOFF_TERMINAL_KEY_TEST:
        return False, "Invalid terminal key"

    logger.debug("Checking order ID...")
    if data.get("OrderId") != order.order_id:
        return False, "Invalid order ID"

    logger.debug("Checking for Payment field status...")
    if data.get("Success", False) is False:
        return False, "Payment failed"

    logger.debug("Checking if payment amount matches the expected value...")
    if data.get("Amount") != int(Decimal(order.amount) * 100):  # Convert rubles to kopecks
        return False, "Amount mismatch"

    token_generator = TinkoffTokenGenerator(terminal_password=settings.TINKOFF_TERMINAL_PASSWORD_TEST)
    payment_token = token_generator.get_token(data)
    # https://docs.python.org/3/library/hmac.html#hmac.HMAC.digest
    logger.debug("Validating token...")
    if not hmac.compare_digest(data.get("Token", ""), payment_token):
        return False, "Invalid token"

    logger.debug("Checking if order is already paid: %s", order.status)
    if order.status == Order.OrderStatus.PAID:
        return False, "Order already paid"

    logger.info("Data validated successfully")
    return True, None


@transaction.atomic
def update_payment_records(data: dict[str, Any], order: Order) -> None:
    """
    Updates the payment records after a successful payment callback.

    Performs multiple tasks:
    1. Updates the given order's status to 'PAID'.
    2. Creates a new Payment record associated with the order and tenant.
    3. Updates the tenant's balance or switches their plan based on order intent.
    4. Sets a new billing start date for tenants who switch to a new plan.

    Args:
        data (Dict[str, Any]): The parsed JSON data from the payment callback containing payment details.
            Expected keys include:
                - "PaymentId" (str): The unique payment identifier.
                - "Amount" (int): The payment amount in kopecks.
                - "ClientName" (optional, str): The name of the client.
        order (Order): The Order object linked to the payment transaction.

    Returns:
        None
    """

    logger.debug("Updating order status to 'PAID'...")
    order.status = Order.OrderStatus.PAID
    order.save()

    amount_rubles = data["Amount"] / 100  # Kopecks to Rubles
    amount_rubles = Decimal(str(amount_rubles))
    logger.debug("amount_rubles has been converted to decimal type: %s", type(amount_rubles))

    logger.debug("Creating payment record...")
    Payment.objects.create(
        tenant=order.tenant,
        order=order,
        payment_id=data["PaymentId"],
        amount=amount_rubles,
        client_name=data.get("ClientName", ""),
        client_email=order.tenant.name,
        is_successful=True,
    )

    # if order.order_intent == Order.OrderIntent.ADD_TO_BALANCE:
    logger.debug("Adding %s rub. to tenant balance...", amount_rubles)
    order.tenant.add_to_balance(amount_rubles)
    if order.order_intent == Order.OrderIntent.SWITCH_PLAN:
        plan_name = order.description
        order.tenant.switch_plan(new_plan=plan_name)
        order.tenant.billing_start_date = timezone.now()
    order.tenant.save()


class TinkoffTokenGenerator:
    """
    API reference: https://www.tbank.ru/kassa/dev/payments/#section/Token

    Generate a token for validating Tinkoff payments based on the terminal_password.
    "terminal_password" - get it from the merchant dashboard

    :Example:
    terminal_password=settings.TINKOFF_TERMINAL_PASSWORD_TEST

    data = {
            "TerminalKey": "TERMINAL_KEY_EXAMPLE",
            "OrderId": "279498",
            "Success": True,
            "Status": "AUTHORIZED",
            "PaymentId": 5278152875,
            "ErrorCode": "0",
            "Amount": 599000,
            "CardId": 493814601,
            "Pan": "XXXX****XXXX1234",
            "ExpDate": "1210",
            "Token": "EXAMPLE_TOKEN",
        }

    generator = TinkoffTokenGenerator(terminal_password)
    print(generator.get_token(data))
    """

    IGNORED_TYPES = (dict, list, tuple)  # Ensures that only non-nested objects are used for token generation

    def __init__(self, terminal_password: str):
        self.password = terminal_password

    def get_raw_token(self, data: dict) -> str:
        """
        Generate a raw token by concatenating values sorted by key.
        """
        # Create a copy of the data to avoid modifying the original, i.e. data["Password"] = self.password
        data_copy = data.copy()
        logger.debug("Creating raw token from data...")
        logger.debug("Adding test password to data...")
        data_copy["Password"] = self.password
        filtered_data = self.filter_data_by_ignored_types(data_copy)

        logger.debug("Sorting filtered data by key...")
        sorted_data = sorted(filtered_data.items(), key=lambda item: item[0])
        logger.debug("Data successfully sorted by key.")
        raw_token = "".join(str(value) for key, value in sorted_data)
        logging.debug("Created raw token string before encoding.")
        return raw_token

    def filter_data_by_ignored_types(self, data: dict) -> dict:
        """
        Filter out nested objects from the data dictionary according to the API docs.
        """
        processed_data = self.convert_boolean_values_to_strings(data)

        logger.debug("Filtering data by ignored types...")
        filtered_data = {
            key: value
            for key, value in processed_data.items()
            if not isinstance(value, self.IGNORED_TYPES)
            if key != "Token"
        }
        logger.debug("Data successfully filtered by ignored types.")
        return filtered_data

    @staticmethod
    def convert_boolean_values_to_strings(data: dict) -> dict:
        """
        Convert boolean values in the incoming data to lowercase strings.
        This is necessary because the API expects boolean values to be lowercase.

        :Example:
            'Success': True -> 'Success': 'true'
        """
        logger.debug("Converting boolean values to strings...")
        processed_data = {key: str(value).lower() if isinstance(value, bool) else value for key, value in data.items()}
        logger.debug("Boolean values successfully converted to strings.")
        return processed_data

    @staticmethod
    def encode_data(data: str) -> str:
        """
        Encode the concatenated string using SHA-256.
        """
        logger.debug("Encoding raw token string")
        encoded_data = hashlib.sha256(data.encode("utf-8")).hexdigest()
        logger.debug("Raw token string successfully encoded.")
        return encoded_data

    def get_token(self, data: dict) -> str:
        """
        Generate the final token after encoding the concatenated string.
        """
        raw_token = self.get_raw_token(data)
        token = self.encode_data(raw_token)
        logger.debug("Token successfully generated.")
        return token
