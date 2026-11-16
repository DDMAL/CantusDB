"""Reconcile institutions and their recoverable revisions with Getty TGN."""

import json
from pathlib import Path

from django.db import migrations, models
import django.db.models.deletion

# This dated catalogue is frozen migration input. Add a new dated file for updates.
CATALOGUE = json.loads(
    (Path(__file__).parent.parent / "data" / "countries_20261115.json").read_text()
)
ALIASES = {
    name.strip().casefold(): row["code"]
    for row in CATALOGUE
    for name in [row["name"], *row["aliases"]]
}


def code_for(value: str | None) -> str | None:
    return ALIASES.get((value or "").strip().casefold())


def institution_versions(apps, alias):
    return (
        apps.get_model("reversion", "Version")
        .objects.using(alias)
        .filter(content_type__app_label="main_app", content_type__model="institution")
    )


def forwards(apps, schema_editor) -> None:
    alias = schema_editor.connection.alias
    Country = apps.get_model("main_app", "Country")
    Institution = apps.get_model("main_app", "Institution")
    institutions = Institution.objects.using(alias)
    unmapped = [
        (pk, value)
        for pk, value in institutions.values_list("pk", "country_text")
        if code_for(value) is None
    ]
    if unmapped:
        raise ValueError(
            f"Reconcile these institution countries before migrating: {unmapped}"
        )
    Country.objects.using(alias).bulk_create(
        [Country(code=row["code"], name=row["name"]) for row in CATALOGUE]
    )
    for institution in institutions.iterator():
        institutions.filter(pk=institution.pk).update(
            country_id=code_for(institution.country_text)
        )

    # The old field contained text. Leaving that text in Version.country would
    # make Django interpret 'USA' as a foreign key and break revision recovery.
    for version in institution_versions(apps, alias).iterator():
        objects = json.loads(version.serialized_data)
        for obj in objects:
            fields = obj["fields"]
            if obj["model"] != "main_app.institution" or "country" not in fields:
                continue
            original = fields["country"]
            # Historical countries outside the catalogue become Unknown.
            fields["country"] = code_for(original) or "unknown"
        version.serialized_data = json.dumps(objects)
        version.save(using=alias, update_fields=["serialized_data"])


def backwards(apps, schema_editor) -> None:
    alias = schema_editor.connection.alias
    Country = apps.get_model("main_app", "Country")
    Institution = apps.get_model("main_app", "Institution")
    names = dict(Country.objects.using(alias).values_list("code", "name"))

    def country_name(code: str) -> str:
        # Restore the old missing-value default, but not discarded spellings.
        return "[No Country]" if code == "not-recorded" else names[code]

    institutions = Institution.objects.using(alias)
    for institution in institutions.iterator():
        institutions.filter(pk=institution.pk).update(
            country_text=country_name(institution.country_id)
        )
    for version in institution_versions(apps, alias).iterator():
        objects = json.loads(version.serialized_data)
        for obj in objects:
            fields = obj["fields"]
            if obj["model"] != "main_app.institution" or "country" not in fields:
                continue
            fields["country"] = country_name(fields["country"])
        version.serialized_data = json.dumps(objects)
        version.save(using=alias, update_fields=["serialized_data"])


class Migration(migrations.Migration):
    dependencies = [
        ("main_app", "0046_incipit_std_spelling"),
        ("reversion", "0002_add_index_on_version_for_content_type_and_db"),
    ]

    operations = [
        migrations.CreateModel(
            name="Country",
            fields=[
                (
                    "code",
                    models.CharField(max_length=32, primary_key=True, serialize=False),
                ),
                ("name", models.CharField(max_length=128, unique=True)),
            ],
            options={"ordering": ["name"], "verbose_name_plural": "countries"},
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
                default="not-recorded",
                on_delete=django.db.models.deletion.PROTECT,
                to="main_app.country",
            ),
        ),
        migrations.AlterModelOptions(
            name="institution",
            options={"ordering": ["country__name", "city", "name"]},
        ),
    ]
