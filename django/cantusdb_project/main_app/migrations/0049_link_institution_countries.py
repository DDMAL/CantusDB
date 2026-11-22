"""Link legacy institution country text and saved revisions to the loaded catalogue."""

import json

from django.db import migrations, models


def convert_versions(apps, db, convert):
    versions = (
        apps.get_model("reversion", "Version")
        .objects.using(db)
        .filter(content_type__app_label="main_app", content_type__model="institution")
    )
    batch = []
    for version in versions.iterator():
        objects = json.loads(version.serialized_data)
        changed = False
        for obj in objects:
            fields = obj["fields"]
            if obj["model"] == "main_app.institution" and "country" in fields:
                old = fields["country"]
                new = convert(old)
                if old != new:
                    fields["country"] = new
                    changed = True
        if changed:
            version.serialized_data = json.dumps(objects)
            batch.append(version)
        if len(batch) == 500:
            versions.bulk_update(batch, ["serialized_data"])
            batch.clear()
    if batch:
        versions.bulk_update(batch, ["serialized_data"])


def from_text(apps, schema_editor):
    db = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(db)
    institutions = apps.get_model("main_app", "Institution").objects.using(db)
    ids = {}
    for pk, name, aliases, code in countries.values_list(
        "pk", "name", "aliases", "rism_code"
    ):
        for label in (name, *aliases.splitlines(), code):
            if label:
                key = label.strip().casefold()
                if ids.setdefault(key, pk) != pk:
                    raise ValueError(
                        f"Ambiguous country {label!r}. Correct the country names, aliases or RISM codes and retry."
                    )

    missing = set()

    def country_id(value):
        label = (value or "").strip()
        key = label.casefold()
        if key in ("", "[no country]", "not recorded"):
            return None
        if not ids:
            raise ValueError(
                "Run python manage.py load_countries before migrating existing institution countries, then run migrate again."
            )
        if key in ("unknown", "[unknown country]"):
            if "unknown" not in ids:
                ids["unknown"] = countries.create(name="Unknown").pk
            return ids["unknown"]
        if key not in ids:
            missing.add(label)
        return ids.get(key)

    values = institutions.order_by().values_list("country_text", flat=True).distinct()
    for value in list(values):
        institutions.filter(country_text=value).update(country_id=country_id(value))
    convert_versions(apps, db, country_id)
    if missing:
        labels = ", ".join(repr(label) for label in sorted(missing))
        raise ValueError(
            f"Unmatched institution countries in records or revisions: {labels}. Add the missing countries or aliases and run migrate again."
        )
    # PostgreSQL must finish deferred FK checks before changing this table again.
    schema_editor.connection.check_constraints()


def to_text(apps, schema_editor):
    db = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(db)
    institutions = apps.get_model("main_app", "Institution").objects.using(db)
    names = dict(countries.values_list("pk", "name"))
    names[None] = "[No Country]"
    for pk, name in names.items():
        institutions.filter(country_id=pk).update(country_text=name)
    convert_versions(
        apps, db, lambda value: names[int(value) if value is not None else None]
    )
    schema_editor.connection.check_constraints()


class Migration(migrations.Migration):
    dependencies = [
        ("main_app", "0048_create_country"),
        ("reversion", "0002_add_index_on_version_for_content_type_and_db"),
    ]
    operations = [
        migrations.RenameField("institution", "country", "country_text"),
        migrations.AddField(
            model_name="institution",
            name="country",
            field=models.ForeignKey(
                blank=True, null=True, on_delete=models.PROTECT, to="main_app.country"
            ),
        ),
        migrations.AlterModelOptions(
            name="institution", options={"ordering": ["country__name", "city", "name"]}
        ),
        migrations.RunPython(from_text, to_text),
        migrations.RemoveField("institution", "country_text"),
    ]
