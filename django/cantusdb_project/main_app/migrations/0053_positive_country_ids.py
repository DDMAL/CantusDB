from django.db import migrations, models

from ._positive_country_ids import NOT_RECORDED, use_positive_ids, restore_legacy_ids


class Migration(migrations.Migration):
    dependencies = [("main_app", "0052_country_catalogue_loaded")]
    operations = [
        migrations.RunPython(use_positive_ids, restore_legacy_ids),
        migrations.AlterField(
            model_name="institution",
            name="country",
            field=models.ForeignKey(
                default=NOT_RECORDED, on_delete=models.PROTECT, to="main_app.country"
            ),
        ),
        migrations.AddConstraint(
            model_name="country",
            constraint=models.CheckConstraint(
                condition=models.Q(pk__gt=0), name="positive_country_id"
            ),
        ),
    ]
