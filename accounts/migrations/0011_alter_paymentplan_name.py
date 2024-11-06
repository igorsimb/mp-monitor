# Generated by Django 5.0 on 2024-11-04 10:41

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0010_alter_historicaltenant_price_change_threshold_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentplan",
            name="name",
            field=models.CharField(
                choices=[
                    ("0", "ТЕСТОВЫЙ"),
                    ("1", "БЕСПЛАТНЫЙ"),
                    ("2", "БИЗНЕС"),
                    ("3", "ПРОФЕССИОНАЛ"),
                    ("4", "КОРПОРАТИВНЫЙ"),
                ],
                max_length=20,
            ),
        ),
    ]