"""Migrate institution country text and revisions to locally maintained records."""

from django.core.validators import RegexValidator
from django.db import migrations, models
from django.db.models.functions import Lower
import django.db.models.deletion

from main_app.data.countries_v1 import COUNTRIES
from ._institution_country_versions import convert_versions

NOT_RECORDED = -1
UNKNOWN = -2


def forwards(apps, schema_editor):
    alias = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(alias)
    institutions = apps.get_model("main_app", "Institution").objects.using(alias)
    countries.create(pk=NOT_RECORDED, name="Not recorded", aliases="[No Country]")
    countries.create(pk=UNKNOWN, name="Unknown", aliases="[Unknown Country]")
    ids = {
        "": NOT_RECORDED,
        "not recorded": NOT_RECORDED,
        "[no country]": NOT_RECORDED,
        "unknown": UNKNOWN,
        "[unknown country]": UNKNOWN,
    }
    known = {
        label.casefold(): (pk, name, getty_id, aliases)
        for pk, name, getty_id, *aliases in COUNTRIES
        for label in [name, *aliases]
    }

    def country_id(value, *, historical=False):
        text = (value or "").strip()
        key = text.casefold()
        if key in ids:
            return ids[key]
        if historical and key not in known:
            # Old, unmatched text in a revision is not a new selectable country.
            return UNKNOWN
        pk, name, getty_id, aliases = known.get(key, (None, text, None, []))
        country = countries.create(
            pk=pk, name=name, getty_id=getty_id, aliases="\n".join(aliases)
        )
        for label in [name, *aliases]:
            ids[label.casefold()] = country.pk
        return country.pk

    values = (
        institutions.order_by("country_text")
        .values_list("country_text", flat=True)
        .distinct()
    )
    for value in list(values):
        institutions.filter(country_text=value).update(country_id=country_id(value))
    convert_versions(apps, alias, lambda value: country_id(value, historical=True))


def backwards(apps, schema_editor):
    alias = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(alias)
    institutions = apps.get_model("main_app", "Institution").objects.using(alias)
    names = dict(countries.values_list("pk", "name"))
    names[NOT_RECORDED] = "[No Country]"
    for pk, name in names.items():
        institutions.filter(country_id=pk).update(country_text=name)
    convert_versions(apps, alias, lambda value: names[int(value)])


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
        migrations.RunPython(forwards, backwards),
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
