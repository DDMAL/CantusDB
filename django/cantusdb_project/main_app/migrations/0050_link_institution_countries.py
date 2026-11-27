"""Link live institutions to the country catalogue."""

from django.db import migrations


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

    links = {}
    missing = set()
    for value in (
        institutions.order_by().values_list("country_text", flat=True).distinct()
    ):
        label = (value or "").strip()
        key = label.casefold()
        if key in ("", "[no country]", "not recorded"):
            links[value] = None
            continue
        if not ids:
            raise ValueError(
                "Run python manage.py load_countries before migrating existing institution countries, then run migrate again."
            )
        if key in ids:
            links[value] = ids[key]
        else:
            missing.add(label)
    if missing:
        labels = ", ".join(repr(label) for label in sorted(missing))
        raise ValueError(
            f"Unmatched institution countries in records: {labels}. Add the missing countries or aliases and run migrate again."
        )
    for value, pk in links.items():
        institutions.filter(country_text=value).exclude(country_id=pk).update(
            country_id=pk
        )


def to_text(apps, schema_editor):
    db = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(db)
    institutions = apps.get_model("main_app", "Institution").objects.using(db)
    names = dict(countries.values_list("pk", "name"))
    names[None] = "[No Country]"
    for pk, name in names.items():
        institutions.filter(country_id=pk).update(country_text=name)


class Migration(migrations.Migration):
    dependencies = [("main_app", "0049_prepare_institution_countries")]
    operations = [migrations.RunPython(from_text, to_text)]
