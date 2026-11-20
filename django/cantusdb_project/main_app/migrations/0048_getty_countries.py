"""Migrate institution country text and revisions to locally maintained records."""

from django.core.validators import RegexValidator
from django.db import migrations, models
from django.db.models.functions import Lower
import django.db.models.deletion

from ._institution_countries import NOT_RECORDED, from_text, to_text


class Migration(migrations.Migration):
    dependencies = [
        ("main_app", "0047_notation_clavis_sequentiarum_labels"),
        ("reversion", "0002_add_index_on_version_for_content_type_and_db"),
    ]

    operations = [
        migrations.CreateModel(
            name="Country",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=64)),
                (
                    "aliases",
                    models.TextField(
                        blank=True, help_text="Enter one alternate name per line."
                    ),
                ),
                (
                    "getty_id",
                    models.CharField(
                        "Getty TGN ID",
                        max_length=32,
                        blank=True,
                        null=True,
                        unique=True,
                        validators=[
                            RegexValidator(r"^[0-9]+$", "Enter a numeric Getty TGN ID.")
                        ],
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "verbose_name_plural": "countries",
                "constraints": [
                    models.UniqueConstraint(
                        Lower("name"), name="unique_country_name_ci"
                    )
                ],
            },
        ),
        migrations.RenameField("institution", "country", "country_text"),
        migrations.AddField(
            model_name="institution",
            name="country",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to="main_app.country",
            ),
        ),
        migrations.RunPython(from_text, to_text),
        # This temporary column is only needed while mapping the old strings.
        # On reversal Django recreates it before backwards fills canonical names.
        migrations.RemoveField("institution", "country_text"),
        migrations.AlterField(
            model_name="institution",
            name="country",
            field=models.ForeignKey(
                default=NOT_RECORDED,
                on_delete=django.db.models.deletion.PROTECT,
                to="main_app.country",
            ),
        ),
        migrations.AlterModelOptions(
            name="institution",
            options={"ordering": ["country__name", "city", "name"]},
        ),
    ]
