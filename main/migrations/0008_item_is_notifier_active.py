# Generated by Django 5.0 on 2024-09-18 09:32

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0007_alter_payment_receipt_items_alter_payment_testing"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="is_notifier_active",
            field=models.BooleanField(default=False),
        ),
    ]