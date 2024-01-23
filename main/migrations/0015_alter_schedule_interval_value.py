# Generated by Django 4.2.6 on 2024-01-27 20:31

import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0014_alter_schedule_period_alter_schedule_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="schedule",
            name="interval_value",
            field=models.IntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(1)],
                verbose_name="Каждые",
            ),
        ),
    ]
