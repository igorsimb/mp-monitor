# Generated by Django 4.2.6 on 2023-10-20 11:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0003_item_seller_price_alter_item_price_alter_item_sku"),
    ]

    operations = [
        migrations.AlterField(
            model_name="item",
            name="sku",
            field=models.FloatField(blank=True, null=True),
        ),
    ]
