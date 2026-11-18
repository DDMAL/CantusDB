"""Migrate institution country text and revisions to locally maintained records."""

import json

from django.core.validators import RegexValidator
from django.db import migrations, models
from django.db.models.functions import Lower
import django.db.models.deletion

NOT_RECORDED = -1
UNKNOWN = -2

# Getty IDs for names used by Cantus and its legacy imports. These rows are
# reconciliation hints: a country is inserted only when an institution uses it.
# Each row contains the preferred name, TGN ID, and alternate names / RISM sigla.
LEGACY_COUNTRIES = (
    ("Argentina", "7006477", "RA"),
    ("Australia", "7000490", "AUS"),
    ("Austria", "1000062", "A"),
    ("Belgium", "1000063", "B"),
    ("Brazil", "1000047", "BR"),
    ("Canada", "7005685", "CDN", "CA", "CAN"),
    ("China", "1000111", "CN", "CHN", "People's Republic of China"),
    ("Croatia", "7006663", "HR"),
    ("Czech Republic", "1001780", "CZ", "Czechia"),
    ("Denmark", "1000066", "DK"),
    ("Ecuador", "1000051", "EC"),
    ("Finland", "1000069", "FIN"),
    ("France", "1000070", "F"),
    ("Germany", "7000084", "D"),
    ("Greece", "1000074", "GR"),
    ("Holy See", "7001168", "V", "Vatican City", "Vatican"),
    ("Hungary", "7006278", "H"),
    ("Ireland", "1000078", "IRL"),
    ("Italy", "1000080", "I"),
    ("Japan", "1000120", "J"),
    ("Netherlands", "7016845", "NL", "The Netherlands"),
    ("New Zealand", "1000226", "NZ"),
    ("Norway", "1000088", "N"),
    ("Poland", "7006366", "PL"),
    ("Portugal", "1000090", "P"),
    ("Romania", "1000091", "RO"),
    ("Slovakia", "7011765", "SK"),
    ("Slovenia", "7006670", "SI"),
    ("South Africa", "1000193", "ZA"),
    ("Spain", "1000095", "E"),
    ("Sweden", "1000097", "S"),
    ("Switzerland", "7011731", "CH"),
    ("Taiwan", "1000141", "RC"),
    ("Turkey", "1000144", "TR", "Türkiye"),
    ("United Kingdom", "7008591", "GB", "UK", "U.K.", "GBR", "Great Britain"),
    ("United States", "7012149", "US", "USA", "United States of America"),
)


def institution_versions(apps, alias):
    return (
        apps.get_model("reversion", "Version")
        .objects.using(alias)
        .filter(content_type__app_label="main_app", content_type__model="institution")
    )


def convert_versions(apps, alias, convert):
    for version in institution_versions(apps, alias).iterator():
        objects = json.loads(version.serialized_data)
        for obj in objects:
            fields = obj["fields"]
            if obj["model"] == "main_app.institution" and "country" in fields:
                fields["country"] = convert(fields["country"])
        version.serialized_data = json.dumps(objects)
        version.save(using=alias, update_fields=["serialized_data"])


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
        label.casefold(): (name, getty_id, aliases)
        for name, getty_id, *aliases in LEGACY_COUNTRIES
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
        name, getty_id, aliases = known.get(key, (text, None, []))
        country = countries.create(
            name=name, getty_id=getty_id, aliases="\n".join(aliases)
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
