# Generated by Django 4.2.6 on 2023-12-29 00:35

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0007_alter_item_sku"),
    ]

    operations = [
        migrations.AddField(
            model_name="item",
            name="is_in_stock",
            field=models.BooleanField(default=True),
        ),
    ]