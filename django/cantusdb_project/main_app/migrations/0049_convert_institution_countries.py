"""Translate existing institution records and saved revisions from text to country IDs."""

import json

from django.db import migrations

# Frozen legacy spellings and their permanent Cantus IDs. Only represented countries
# are created here. The loader owns the editable catalogue and its authority data.
COUNTRIES = (
    (1, "Argentina", "RA"),
    (2, "Australia", "AUS"),
    (3, "Austria", "A"),
    (4, "Belgium", "B"),
    (5, "Brazil", "BR"),
    (6, "Canada", "CDN", "CA", "CAN"),
    (7, "China", "CN", "CHN", "People's Republic of China"),
    (8, "Croatia", "HR"),
    (9, "Czech Republic", "CZ", "Czechia"),
    (10, "Denmark", "DK"),
    (11, "Ecuador", "EC"),
    (12, "Finland", "FIN"),
    (13, "France", "F"),
    (14, "Germany", "D"),
    (15, "Greece", "GR"),
    (16, "Holy See", "V", "Vatican City", "Vatican"),
    (17, "Hungary", "H"),
    (18, "Ireland", "IRL"),
    (19, "Italy", "I"),
    (20, "Japan", "J"),
    (21, "Netherlands", "NL", "The Netherlands"),
    (22, "New Zealand", "NZ"),
    (23, "Norway", "N"),
    (24, "Poland", "PL"),
    (25, "Portugal", "P"),
    (26, "Romania", "RO"),
    (27, "Slovakia", "SK"),
    (28, "Slovenia", "SI"),
    (29, "South Africa", "ZA"),
    (30, "Spain", "E"),
    (31, "Sweden", "S"),
    (32, "Switzerland", "CH"),
    (33, "Taiwan", "RC"),
    (34, "Turkey", "TR", "Türkiye"),
    (35, "United Kingdom", "GB", "UK", "U.K.", "GBR", "Great Britain"),
    (36, "United States of America", "US", "USA", "United States"),
)


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
    catalogue = {
        label.casefold(): (pk, name)
        for pk, name, *aliases in COUNTRIES
        for label in (name, *aliases)
    }
    ids = {name.casefold(): pk for pk, name in countries.values_list("pk", "name")}

    def country_id(value, *, historical=False):
        label = (value or "").strip()
        key = label.casefold()
        if key in ("", "[no country]", "not recorded"):
            return None
        if key in ids:
            return ids[key]
        if key in catalogue:
            pk, name = catalogue[key]
            countries.get_or_create(pk=pk, defaults={"name": name})
        else:
            # A historical typo must not become a selectable country. Current
            # local names have already been indexed before we convert revisions.
            name = (
                "Unknown"
                if historical or key in ("[unknown country]", "unknown")
                else label
            )
            pk = ids.get(name.casefold())
            if pk is None:
                pk = countries.create(name=name).pk
        ids[key] = pk
        ids[name.casefold()] = pk
        return pk

    values = (
        institutions.order_by("country_text")
        .values_list("country_text", flat=True)
        .distinct()
    )
    for value in list(values):
        institutions.filter(country_text=value).update(country_id=country_id(value))
    convert_versions(apps, db, lambda value: country_id(value, historical=True))


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


class Migration(migrations.Migration):
    dependencies = [
        ("main_app", "0048_country"),
        ("reversion", "0002_add_index_on_version_for_content_type_and_db"),
    ]
    operations = [migrations.RunPython(from_text, to_text)]
