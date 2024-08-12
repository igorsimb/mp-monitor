import base64
import hashlib
import os


secret_key = os.environ.get("PAYMENT_TEST_SECRET_KEY")
merchant_id = os.environ.get("PAYMENT_MERCHANT_ID")


def get_raw_signature(params):
    chunks = []

    for key in sorted(params.keys()):
        if key == "signature":
            continue

        value = params[key]

        if isinstance(value, str):
            value = value.encode("utf8")
        else:
            value = str(value).encode("utf-8")

        if not value:
            continue

        value_encoded = base64.b64encode(value)
        chunks.append("%s=%s" % (key, value_encoded.decode()))

    raw_signature = "&".join(chunks)
    return raw_signature


"""Двойное шифрование sha1 на основе секретного ключа"""


def double_sha1(secret_key, data):
    sha1_hex = lambda s: hashlib.sha1(s.encode("utf-8")).hexdigest()  # noqa
    digest = sha1_hex(secret_key + sha1_hex(secret_key + data))
    return digest


"""Вычисляем подпись (signature). Подпись считается на основе склеенной строки из отсортированного массива параметров, исключая из расчета пустые поля и элемент "signature" """


def get_signature(secret_key: str, params: dict) -> str:
    return double_sha1(secret_key, get_raw_signature(params))


"""Определяем словарь с параметрами для расчета.
В этот массив должны войти все параметры, отправляемые в вашей форме (за исключением самого поля signature, значение которого вычисляем).
Получив вашу форму, система ИЭ аналогичным образом вычислит из ее параметров signature и сравнит значение с вычисленным на стороне вашего магазина.
подставьте ваш секретный ключ вместо 00112233445566778899aabbccddeeff
"""
if __name__ == "__main__":
    # amount = sum of all items in receipt_items
    # e.g. item1 = 10 items * 48 price - 40 discount = 440
    #      item2 = 1 item * 533 price = 533
    # amount = 440 + 533 = 973
    # BUT receipt_items is only needed to create a receipt, which we don't need
    items = {
        "testing": "1",
        "salt": "xafAFruTVrpwHKjvZoHvSVkUeMqZoefp",
        "order_id": "43683694",
        "amount": "555",
        "merchant": merchant_id,
        "description": "Заказ №43683693",
        "client_phone": "+7 (700) 675-87-89",
        "client_email": "test@test.ru",
        "client_name": "Тестов Тест Тестович",
        "success_url": "https://pay.modulbank.ru/success",
        # "receipt_contact": "test@mail.com",
        # "receipt_items": (
        #     '[{"discount_sum": 40, "name": "Товар 1", "payment_method": "full_prepayment", "payment_object":'
        #     ' "commodity", "price": 48, "quantity": 10, "sno": "osn", "vat": "vat10"}, {"name": "Товар 2",'
        #     ' "payment_method": "full_prepayment", "payment_object": "commodity", "price": 533, "quantity": 1, "sno":'
        #     ' "osn", "vat": "vat10"}]'
        # ),
        "unix_timestamp": "1723447580",
    }
    # print(get_signature('00112233445566778899aabbccddeeff', items))
    print(get_signature(secret_key, items))
