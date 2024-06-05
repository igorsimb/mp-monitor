# Generated by Django 5.0 on 2024-05-08 16:55

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_alter_customuser_options"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="userquota",
            options={"verbose_name": "Квота", "verbose_name_plural": "Квоты"},
        ),
        migrations.RenameField(
            model_name="userquota",
            old_name="max_skus",
            new_name="max_allowed_skus",
        ),
    ]