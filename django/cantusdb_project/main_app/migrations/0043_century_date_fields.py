# Generated migration for adding date fields to Century model

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("main_app", "0042_source_source_data_contributed_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="century",
            name="min_date",
            field=models.IntegerField(
                null=True,
                blank=True,
                help_text="Start year of century (e.g., 1400 for 15th century)",
            ),
        ),
        migrations.AddField(
            model_name="century",
            name="max_date",
            field=models.IntegerField(
                null=True,
                blank=True,
                help_text="End year of century (e.g., 1499 for 15th century)",
            ),
        ),
    ]
