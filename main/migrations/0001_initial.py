# Generated by Django 4.2.10 on 2024-04-15 10:57

from django.conf import settings
import django.core.validators
from django.db import migrations, models
import django.db.models.deletion
import simple_history.models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
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
            ],
            options={
                "verbose_name": "Товар",
                "verbose_name_plural": "Товары",
                "permissions": (("view_item", "Can view item"),),
                "default_permissions": ("add", "change", "delete"),
            },
        ),
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
                            ("seconds", "Секунд"),
                            ("minutes", "Минут"),
                            ("hours", "Часов"),
                            ("days", "Дней"),
                        ],
                        default="hours",
                        max_length=100,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Tenant",
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
                ("name", models.CharField(max_length=255, unique=True)),
                (
                    "status",
                    models.IntegerField(
                        choices=[
                            (1, "Trialing"),
                            (2, "Active"),
                            (3, "Exempt"),
                            (4, "Canceled"),
                            (5, "Trial expired"),
                        ],
                        default=1,
                    ),
                ),
            ],
            options={
                "verbose_name": "Организация",
                "verbose_name_plural": "Организации",
                "indexes": [models.Index(fields=["status"], name="main_tenant_status_883ca8_idx")],
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
        migrations.AddField(
            model_name="item",
            name="tenant",
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="main.tenant"),
        ),
        migrations.CreateModel(
            name="HistoricalTenant",
            fields=[
                (
                    "id",
                    models.BigIntegerField(auto_created=True, blank=True, db_index=True, verbose_name="ID"),
                ),
                ("name", models.CharField(db_index=True, max_length=255)),
                (
                    "status",
                    models.IntegerField(
                        choices=[
                            (1, "Trialing"),
                            (2, "Active"),
                            (3, "Exempt"),
                            (4, "Canceled"),
                            (5, "Trial expired"),
                        ],
                        default=1,
                    ),
                ),
                ("history_id", models.AutoField(primary_key=True, serialize=False)),
                ("history_date", models.DateTimeField(db_index=True)),
                ("history_change_reason", models.CharField(max_length=100, null=True)),
                (
                    "history_type",
                    models.CharField(
                        choices=[("+", "Created"), ("~", "Changed"), ("-", "Deleted")],
                        max_length=1,
                    ),
                ),
                (
                    "history_user",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "historical Организация",
                "verbose_name_plural": "historical Организации",
                "ordering": ("-history_date", "-history_id"),
                "get_latest_by": ("history_date", "history_id"),
            },
            bases=(simple_history.models.HistoricalChanges, models.Model),
        ),
        migrations.AddConstraint(
            model_name="price",
            constraint=models.CheckConstraint(check=models.Q(("value__gte", 0)), name="no_negative_price_value"),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.UniqueConstraint(fields=("tenant", "sku"), name="unique_tenant_sku"),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.CheckConstraint(check=models.Q(("price__gte", 0.0)), name="no_negative_price"),
        ),
    ]
