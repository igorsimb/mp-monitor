# Generated by Django 5.0 on 2024-08-20 17:36

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0006_payment_receipt_items"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="receipt_items",
            field=models.CharField(blank=True, max_length=2550, null=True),
        ),
        migrations.AlterField(
            model_name="payment",
            name="testing",
            field=models.CharField(default="0", max_length=1),
        ),
    ]