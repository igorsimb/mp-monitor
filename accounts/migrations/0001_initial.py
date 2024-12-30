# Generated by Django 5.1.4 on 2024-12-29 17:19

import accounts.models
import django.contrib.auth.models
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
import simple_history.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
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
                            ("0", "ТЕСТОВЫЙ"),
                            ("1", "БЕСПЛАТНЫЙ"),
                            ("2", "БИЗНЕС"),
                            ("3", "ПРОФЕССИОНАЛ"),
                            ("4", "КОРПОРАТИВНЫЙ"),
                        ],
                        max_length=20,
                    ),
                ),
                (
                    "price",
                    models.DecimalField(decimal_places=2, default=0.0, max_digits=10),
                ),
            ],
        ),
        migrations.CreateModel(
            name="TenantQuota",
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
                        blank=True,
                        choices=[
                            ("0", "КВОТА ТЕСТОВАЯ"),
                            ("1", "КВОТА БЕСПЛАТНАЯ"),
                            ("2", "КВОТА БИЗНЕС"),
                            ("3", "КВОТА ПРОФЕССИОНАЛ"),
                            ("4", "КВОТА КОРПОРАТИВНАЯ"),
                        ],
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "total_hours_allowed",
                    models.PositiveIntegerField(blank=True, default=1440, null=True),
                ),
                (
                    "skus_limit",
                    models.PositiveIntegerField(blank=True, default=10, null=True),
                ),
                (
                    "parse_units_limit",
                    models.PositiveIntegerField(blank=True, default=10, null=True),
                ),
            ],
            options={
                "verbose_name": "Квота",
                "verbose_name_plural": "Квоты",
            },
        ),
        migrations.CreateModel(
            name="User",
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
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        unique=True,
                        validators=[
                            django.contrib.auth.validators.UnicodeUsernameValidator()
                        ],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, verbose_name="email address"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("is_demo_user", models.BooleanField(default=False)),
                ("is_demo_active", models.BooleanField(default=False)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "Пользователь",
                "verbose_name_plural": "Пользователи",
            },
            managers=[
                ("objects", django.contrib.auth.models.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="Profile",
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
                    "image",
                    models.ImageField(blank=True, null=True, upload_to="avatars/"),
                ),
                (
                    "display_name",
                    models.CharField(blank=True, max_length=40, null=True),
                ),
                ("info", models.TextField(blank=True, null=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        to=settings.AUTH_USER_MODEL,
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
                        default=2,
                    ),
                ),
                (
                    "balance",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        null=True,
                    ),
                ),
                ("billing_start_date", models.DateField(blank=True, null=True)),
                (
                    "price_change_threshold",
                    models.DecimalField(
                        decimal_places=2,
                        default=0.0,
                        help_text="Процент изменения цены для уведомлений (напр, 5.00%)",
                        max_digits=6,
                    ),
                ),
                (
                    "payment_plan",
                    models.ForeignKey(
                        default=accounts.models.PaymentPlan.get_default_payment_plan,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="accounts.paymentplan",
                    ),
                ),
                (
                    "quota",
                    models.ForeignKey(
                        blank=True,
                        default=accounts.models.TenantQuota.get_default_quota,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="tenants",
                        to="accounts.tenantquota",
                    ),
                ),
            ],
            options={
                "verbose_name": "Организация",
                "verbose_name_plural": "Организации",
            },
        ),
        migrations.AddField(
            model_name="user",
            name="tenant",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="users",
                to="accounts.tenant",
                verbose_name="Организация",
            ),
        ),
        migrations.AddField(
            model_name="paymentplan",
            name="quotas",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="accounts.tenantquota",
            ),
        ),
        migrations.CreateModel(
            name="HistoricalTenant",
            fields=[
                (
                    "id",
                    models.BigIntegerField(
                        auto_created=True, blank=True, db_index=True, verbose_name="ID"
                    ),
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
                        default=2,
                    ),
                ),
                (
                    "balance",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        default=0,
                        max_digits=10,
                        null=True,
                    ),
                ),
                ("billing_start_date", models.DateField(blank=True, null=True)),
                (
                    "price_change_threshold",
                    models.DecimalField(
                        decimal_places=2,
                        default=0.0,
                        help_text="Процент изменения цены для уведомлений (напр, 5.00%)",
                        max_digits=6,
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
                (
                    "payment_plan",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        default=accounts.models.PaymentPlan.get_default_payment_plan,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="accounts.paymentplan",
                    ),
                ),
                (
                    "quota",
                    models.ForeignKey(
                        blank=True,
                        db_constraint=False,
                        default=accounts.models.TenantQuota.get_default_quota,
                        null=True,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="+",
                        to="accounts.tenantquota",
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
        migrations.AddIndex(
            model_name="user",
            index=models.Index(
                fields=["tenant"], name="accounts_us_tenant__b29105_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="tenant",
            index=models.Index(fields=["status"], name="accounts_te_status_28aa65_idx"),
        ),
    ]
