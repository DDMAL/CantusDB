# Generated by Django 4.2.11 on 2024-07-17 14:27

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0024_merge_20240714_2153"),
    ]

    operations = [
        migrations.AlterField(
            model_name="source",
            name="date",
            field=models.CharField(
                blank=True,
                help_text='Date of the source, if known (e.g. "1541")',
                max_length=63,
                null=True,
            ),
        ),
    ]
