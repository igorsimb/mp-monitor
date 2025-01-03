# Generated by Django 5.1.4 on 2024-12-29 17:19

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
                    models.CharField(blank=True, max_length=100, null=True, verbose_name="CronJob"),
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
                ("is_notifier_active", models.BooleanField(default=False)),
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
            name="Order",
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
                ("order_id", models.CharField(blank=True, max_length=255, unique=True)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                (
                    "description",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "order_intent",
                    models.CharField(
                        choices=[
                            ("SWITCH_PLAN", "Switch plan"),
                            ("ADD_TO_BALANCE", "Add to balance"),
                        ],
                        default="ADD_TO_BALANCE",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("PENDING", "Pending"),
                            ("PAID", "Paid"),
                            ("PROCESSING", "Processing"),
                            ("COMPLETED", "Completed"),
                            ("CANCELED", "Canceled"),
                            ("FAILED", "Failed"),
                            ("REFUNDED", "Refunded"),
                        ],
                        default="PENDING",
                        max_length=20,
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="accounts.tenant",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Payment",
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
                ("merchant", models.CharField(max_length=255)),
                ("terminal_key", models.CharField(max_length=255)),
                (
                    "payment_id",
                    models.CharField(blank=True, max_length=255, unique=True),
                ),
                (
                    "amount",
                    models.DecimalField(decimal_places=2, max_digits=10, verbose_name="Сумма оплаты"),
                ),
                (
                    "client_name",
                    models.CharField(
                        blank=True,
                        help_text="ФИО плательщика",
                        max_length=255,
                        null=True,
                    ),
                ),
                ("client_email", models.CharField(max_length=255)),
                (
                    "client_phone",
                    models.CharField(blank=True, max_length=15, null=True),
                ),
                (
                    "testing",
                    models.CharField(choices=[("1", "1"), ("0", "0")], default="0", max_length=1),
                ),
                ("is_successful", models.BooleanField(default=False)),
                (
                    "order",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="payments",
                        to="main.order",
                    ),
                ),
                (
                    "tenant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="accounts.tenant",
                    ),
                ),
            ],
            options={
                "ordering": ["-id"],
            },
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
            constraint=models.UniqueConstraint(fields=("tenant", "sku"), name="unique_tenant_sku"),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.CheckConstraint(condition=models.Q(("price__gte", 0.0)), name="no_negative_price"),
        ),
        migrations.AddConstraint(
            model_name="price",
            constraint=models.CheckConstraint(condition=models.Q(("value__gte", 0)), name="no_negative_price_value"),
        ),
    ]
