"""Link live institutions to the country catalogue."""

from django.db import migrations, models


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
    if missing:
        labels = ", ".join(repr(label) for label in sorted(missing))
        raise ValueError(
            f"Unmatched institution countries in records: {labels}. Add the missing countries or aliases and run migrate again."
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
    schema_editor.connection.check_constraints()


class Migration(migrations.Migration):
    dependencies = [("main_app", "0048_create_country")]
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
