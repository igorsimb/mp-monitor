import hmac

from django.core.management.base import BaseCommand

from utils.payment import TinkoffTokenGenerator


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

        # example from https://tokentcs.web.app/ with terminal_password="test_terminal_password"
        data2 = {
            "TerminalKey": "15180119216597",
            "PaymentId": "5353155",
            "Amount": "851500",
            "Receipt": {
                "Email": "ermilove78@mail.ru",
                "Taxation": "osn",
                "Items": [
                    {
                        "Name": "Футболка-поло с золотистым воротничком",
                        "Price": "728000",
                        "Quantity": "1",
                        "Amount": "364000",
                        "Tax": "vat18",
                    }
                ],
            },
            "Token": "44431aec17a9c4fd6bafcfff4580d0168d50ff815a9026c116f53d986cc002b5",
        }

        data = data2
        terminal_password = "test_terminal_password"
        generator = TinkoffTokenGenerator(terminal_password)
        raw_token = generator.get_raw_token(data)
        encoded_token = generator.get_token(data)
        print(f"{raw_token = }")
        print(f"{encoded_token = }")

        if hmac.compare_digest(data.get("Token", ""), encoded_token):
            self.stdout.write(self.style.SUCCESS("SUCCESS: token generated correctly"))
        else:
            self.stdout.write(self.style.ERROR("ERROR: Incorrect token"))
