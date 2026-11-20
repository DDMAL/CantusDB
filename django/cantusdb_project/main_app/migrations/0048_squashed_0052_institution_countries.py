from django.db import migrations, models
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Lower

from ._country_authority_urls import unique_authority_urls
from ._institution_countries import NOT_RECORDED, from_text, to_text


class Migration(migrations.Migration):
    replaces = [
        ("main_app", "0048_getty_countries"),
        ("main_app", "0049_country_authorities"),
        ("main_app", "0050_reconcile_wikidata_country_ids"),
        ("main_app", "0051_country_authority_urls"),
        ("main_app", "0052_country_catalogue_loaded"),
    ]
    dependencies = [
        ("main_app", "0047_notation_clavis_sequentiarum_labels"),
        ("admin", "0003_logentry_add_action_flag_choices"),
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
                    "catalogue_loaded",
                    models.BooleanField(default=False, editable=False),
                ),
                (
                    "authorities",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Enter database names and full record URLs. Getty TGN and Wikidata also accept short IDs. "
                        'Example for Canada: {"GeoNames": "https://www.geonames.org/6251999/", "wikidata": "Q16"}.',
                    ),
                ),
            ],
            options={
                "ordering": ["name"],
                "verbose_name_plural": "countries",
                "constraints": [
                    models.UniqueConstraint(
                        Lower("name"), name="unique_country_name_ci"
                    ),
                    models.UniqueConstraint(
                        KeyTextTransform("getty_tgn", "authorities"),
                        name="unique_country_getty_tgn",
                    ),
                    models.UniqueConstraint(
                        KeyTextTransform("wikidata", "authorities"),
                        name="unique_country_wikidata",
                    ),
                ],
            },
        ),
        migrations.RenameField(
            model_name="institution", old_name="country", new_name="country_text"
        ),
        migrations.AddField(
            model_name="institution",
            name="country",
            field=models.ForeignKey(
                null=True, on_delete=models.PROTECT, to="main_app.country"
            ),
        ),
        migrations.RunPython(from_text, to_text),
        migrations.RemoveField(model_name="institution", name="country_text"),
        migrations.AlterField(
            model_name="institution",
            name="country",
            field=models.ForeignKey(
                default=NOT_RECORDED, on_delete=models.PROTECT, to="main_app.country"
            ),
        ),
        migrations.AlterModelOptions(
            name="institution", options={"ordering": ["country__name", "city", "name"]}
        ),
        unique_authority_urls,
    ]
