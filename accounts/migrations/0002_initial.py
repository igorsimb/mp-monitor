# Generated by Django 5.0 on 2024-06-29 15:19

import django.db.models.deletion
import main.models
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
        ("main", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicaltenant",
            name="payment_plan",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                default=main.models.PaymentPlan.get_default_payment_plan,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="main.paymentplan",
            ),
        ),
        migrations.AddField(
            model_name="tenant",
            name="payment_plan",
            field=models.ForeignKey(
                default=main.models.PaymentPlan.get_default_payment_plan,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="main.paymentplan",
            ),
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
            model_name="tenant",
            name="quota",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tenants",
                to="accounts.tenantquota",
            ),
        ),
        migrations.AddField(
            model_name="historicaltenant",
            name="quota",
            field=models.ForeignKey(
                blank=True,
                db_constraint=False,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name="+",
                to="accounts.tenantquota",
            ),
        ),
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["tenant"], name="accounts_us_tenant__b29105_idx"),
        ),
        migrations.AddIndex(
            model_name="tenant",
            index=models.Index(fields=["status"], name="accounts_te_status_28aa65_idx"),
        ),
    ]
