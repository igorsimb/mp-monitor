# Generated by Django 5.0 on 2024-06-29 15:19

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Schedule",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[("interval", "Интервал"), ("cronjob", "CronJob")],
                        default="interval",
                        max_length=50,
                        verbose_name="Тип расписания",
                    ),
                ),
                (
                    "interval_value",
                    models.IntegerField(
                        blank=True,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(1)],
                        verbose_name="Каждые",
                    ),
                ),
                (
                    "cronjob_value",
                    models.CharField(
                        blank=True, max_length=100, null=True, verbose_name="CronJob"
                    ),
                ),
                (
                    "period",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("seconds", "Секунды"),
                            ("minutes", "Минуты"),
                            ("hours", "Часы"),
                            ("days", "Дни"),
                        ],
                        default="hours",
                        max_length=100,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Item",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("sku", models.CharField(max_length=20)),
                (
                    "seller_price",
                    models.DecimalField(
                        decimal_places=0,
                        help_text="Цена товара от продавца",
                        max_digits=10,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0.0)],
                    ),
                ),
                (
                    "price",
                    models.DecimalField(
                        decimal_places=0,
                        help_text="Цена товара в магазине с учетом СПП",
                        max_digits=10,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0.0)],
                    ),
                ),
                ("spp", models.IntegerField(blank=True, null=True)),
                ("image", models.URLField(blank=True, null=True)),
                ("category", models.CharField(blank=True, max_length=255, null=True)),
                ("brand", models.CharField(blank=True, max_length=255, null=True)),
                (
                    "seller_name",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                ("rating", models.FloatField(blank=True, null=True)),
                ("num_reviews", models.IntegerField(blank=True, null=True)),
                ("is_parser_active", models.BooleanField(default=False)),
                ("schedule", models.CharField(blank=True, max_length=255, null=True)),
                ("is_in_stock", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="accounts.tenant",
                    ),
                ),
            ],
            options={
                "verbose_name": "Товар",
                "verbose_name_plural": "Товары",
                "permissions": (("view_item", "Can view item"),),
                "default_permissions": ("add", "change", "delete"),
            },
        ),
        migrations.CreateModel(
            name="PaymentPlan",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "name",
                    models.CharField(
                        choices=[
                            ("FREE", "Free"),
                            ("BUSINESS", "Business"),
                            ("PROFESSIONAL", "Professional"),
                            ("CORPORATE", "Corporate"),
                        ],
                        max_length=20,
                        unique=True,
                    ),
                ),
                (
                    "price",
                    models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
                ),
                (
                    "quotas",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        to="accounts.tenantquota",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Price",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "value",
                    models.DecimalField(
                        decimal_places=0,
                        max_digits=10,
                        null=True,
                        validators=[django.core.validators.MinValueValidator(0.0)],
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="prices",
                        to="main.item",
                    ),
                ),
            ],
            options={
                "verbose_name": "Цена",
                "verbose_name_plural": "Цены",
                "ordering": ["-created_at"],
                "permissions": (("view_item", "Can view item"),),
                "default_permissions": ("add", "change", "delete"),
            },
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(
                fields=("tenant", "sku"), name="unique_tenant_sku"
            ),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.CheckConstraint(
                check=models.Q(("price__gte", 0.0)), name="no_negative_price"
            ),
        ),
        migrations.AddConstraint(
            model_name="price",
            constraint=models.CheckConstraint(
                check=models.Q(("value__gte", 0)), name="no_negative_price_value"
            ),
        ),
    ]
