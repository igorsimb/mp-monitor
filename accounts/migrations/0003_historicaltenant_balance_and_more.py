# Generated by Django 5.0 on 2024-08-19 08:37

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_alter_historicaltenant_quota_alter_tenant_quota"),
    ]

    operations = [
        migrations.AddField(
            model_name="historicaltenant",
            name="balance",
            field=models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="historicaltenant",
            name="billing_start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="balance",
            field=models.DecimalField(blank=True, decimal_places=2, default=0, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="tenant",
            name="billing_start_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
