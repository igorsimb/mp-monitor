# Generated by Django 5.0 on 2024-08-19 13:49

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0005_rename_merchant_id_payment_merchant_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="payment",
            name="receipt_items",
            field=models.TextField(blank=True, null=True),
        ),
    ]
