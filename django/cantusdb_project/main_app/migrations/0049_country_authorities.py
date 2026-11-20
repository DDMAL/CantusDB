"""Preserve country links and revision history on databases that ran the earlier PR."""

from django.db import migrations, models
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import JSONObject

from main_app.data.countries_v1 import matching_ids
from ._institution_country_versions import convert_versions


def copy_identifiers(apps, schema_editor):
    countries = apps.get_model("main_app", "Country").objects.using(
        schema_editor.connection.alias
    )
    countries.exclude(getty_id__isnull=True).exclude(getty_id="").update(
        authorities=JSONObject(getty_tgn=models.F("getty_id"))
    )


def restore_getty_ids(apps, schema_editor):
    countries = apps.get_model("main_app", "Country").objects.using(
        schema_editor.connection.alias
    )
    countries.update(getty_id=KeyTextTransform("getty_tgn", "authorities"))


def assign_stable_ids(apps, schema_editor):
    db = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(db)
    institutions = apps.get_model("main_app", "Institution").objects.using(db)
    remap = {}
    occupied = set(countries.filter(pk__lt=0).values_list("pk", flat=True))
    for country in countries.filter(pk__gt=0):
        labels = [country.name, *country.aliases.splitlines()]
        candidates = matching_ids(labels, country.authorities.get("getty_tgn"))
        if not candidates:
            continue  # Locally created countries keep their original IDs.
        if len(candidates) > 1 or candidates & occupied:
            raise ValueError(
                f"Conflicting catalogue identities for {country.name!r}. Check its aliases and Getty ID before migrating."
            )
        new_pk = candidates.pop()
        occupied.add(new_pk)
        remap[country.pk] = new_pk

    if not remap:
        return
    logs = (
        apps.get_model("admin", "LogEntry")
        .objects.using(db)
        .filter(content_type__app_label="main_app", content_type__model="country")
    )
    for old, new in remap.items():
        countries.filter(pk=old).update(id=new)
        institutions.filter(country_id=old).update(country_id=new)
        logs.filter(object_id=str(old)).update(object_id=str(new))

    convert_versions(
        apps,
        db,
        lambda value: remap.get(int(value), value) if value is not None else None,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("main_app", "0048_getty_countries"),
        ("admin", "0003_logentry_add_action_flag_choices"),
    ]
    operations = [
        migrations.AddField(
            model_name="country",
            name="authorities",
            field=models.JSONField(
                default=dict,
                blank=True,
                help_text='Enter authority IDs, for example {"getty_tgn": "7005685", "wikidata": "Q16"}.',
            ),
        ),
        migrations.RunPython(copy_identifiers, restore_getty_ids),
        migrations.RemoveField(model_name="country", name="getty_id"),
        migrations.AddConstraint(
            model_name="country",
            constraint=models.UniqueConstraint(
                KeyTextTransform("getty_tgn", "authorities"),
                name="unique_country_getty_tgn",
            ),
        ),
        migrations.AddConstraint(
            model_name="country",
            constraint=models.UniqueConstraint(
                KeyTextTransform("wikidata", "authorities"),
                name="unique_country_wikidata",
            ),
        ),
        # The older schema also accepts stable IDs, so reverting preserves the
        # keys and all the references that now point to them.
        migrations.RunPython(assign_stable_ids, migrations.RunPython.noop),
    ]
