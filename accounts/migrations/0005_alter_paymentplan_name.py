# Generated by Django 5.0 on 2024-08-23 10:53

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_alter_paymentplan_name"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paymentplan",
            name="name",
            field=models.CharField(
                choices=[
                    ("1", "1 - БЕСПЛАТНЫЙ"),
                    ("2", "2 - БИЗНЕС"),
                    ("3", "3 - ПРОФЕССИОНАЛ"),
                    ("4", "4 - КОРПОРАТИВНЫЙ"),
                ],
                max_length=20,
            ),
        ),
    ]
