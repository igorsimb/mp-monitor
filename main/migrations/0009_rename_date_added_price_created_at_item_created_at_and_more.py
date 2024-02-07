# Generated by Django 4.2.6 on 2024-01-01 17:21

from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0008_item_is_in_stock"),
    ]

    operations = [
        migrations.RenameField(
            model_name="price",
            old_name="date_added",
            new_name="created_at",
        ),
        migrations.AddField(
            model_name="item",
            name="created_at",
            field=models.DateTimeField(
                auto_now_add=True, default=django.utils.timezone.now
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="item",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="price",
            name="updated_at",
            field=models.DateTimeField(auto_now=True),
        ),
    ]