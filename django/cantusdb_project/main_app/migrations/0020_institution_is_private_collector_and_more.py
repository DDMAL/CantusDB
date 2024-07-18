# Generated by Django 4.1.6 on 2024-06-14 13:33

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("main_app", "0019_remove_source_rism_siglum_delete_rismsiglum"),
    ]

    operations = [
        migrations.AddField(
            model_name="institution",
            name="is_private_collector",
            field=models.BooleanField(
                default=False, help_text="Mark this institution as private collector."
            ),
        ),
        migrations.AddField(
            model_name="institution",
            name="private_notes",
            field=models.TextField(
                blank=True,
                help_text="Notes about this institution that are not publicly visible.",
                null=True,
            ),
        ),
    ]