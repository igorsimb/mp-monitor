import hmac

from django.core.management.base import BaseCommand

from main.payment_utils import TinkoffTokenGenerator
from mp_monitor import settings


class Command(BaseCommand):
    help = "Generates test payment token for Tinkoff Pay"

    def handle(self, *args, **kwargs):
        data1 = {  # noqa
            "TerminalKey": "1728466408616DEMO",
            "OrderId": "279498",
            "Success": True,
            "Status": "AUTHORIZED",
            "PaymentId": 5278152875,
            "ErrorCode": "0",
            "Amount": 599000,
            "CardId": 493814601,
            "Pan": "430000******0777",
            "ExpDate": "1210",
            "Token": "bb63941ff95ef9db76cb8702a5487d4ac3d253605580d8ee6065196f4f7e01d4",
        }

        data2 = {  # noqa
            "TerminalKey": "1728466408616DEMO",
            "OrderId": "279498",
            "Success": True,
            "Status": "CONFIRMED",
            "PaymentId": 5278152875,
            "ErrorCode": "0",
            "Amount": 599000,
            "CardId": 493814601,
            "Pan": "430000******0777",
            "ExpDate": "1210",
            "Token": "45fbf8a215f2c3d68bc09a3611e6c0c7a4db4622ae3c5351e74a40927c71cf0b",
        }

        data = data1
        terminal_password = settings.TINKOFF_TERMINAL_PASSWORD_TEST
        generator = TinkoffTokenGenerator(terminal_password)
        raw_token = generator.get_raw_token(data)
        encoded_token = generator.get_token(data)
        print(f"{raw_token = }")
        print(f"{encoded_token = }")

        if hmac.compare_digest(data.get("Token", ""), encoded_token):
            self.stdout.write(self.style.SUCCESS("SUCCESS: Correct token generated"))
        else:
            self.stdout.write(self.style.ERROR("ERROR: Incorrect token"))
