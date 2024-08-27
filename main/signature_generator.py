import json
import os

import django
from django.conf import settings

# Set up Django environment
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mp_monitor.settings")
django.setup()

from main.utils import MerchantSignatureGenerator  # noqa

if __name__ == "__main__":
    generator = MerchantSignatureGenerator(settings.PAYMENT_TEST_SECRET_KEY)
    receipt_items = json.dumps(
        [
            {
                "name": "ПРОФЕССИОНАЛ",
                "payment_method": "full_prepayment",
                "payment_object": "service",
                "price": "11990.00",
                "quantity": "1",
                "sno": "osn",
                "vat": "none",
            }
        ]
    )
    params = {
        "merchant": "f29e4787-0c3b-4630-9340-5dcfcdc9f85d",
        "unix_timestamp": "1724759108",
        "amount": "11990.00",
        "testing": "1",
        "description": "Абонентская оплата. Тариф: ПРОФЕССИОНАЛ",
        "order_id": "222618",
        "client_email": "admin@gmail.com",
        "success_url": "https://pay.modulbank.ru/success",
        "receipt_items": receipt_items,
    }
    print(generator.get_signature(params))
