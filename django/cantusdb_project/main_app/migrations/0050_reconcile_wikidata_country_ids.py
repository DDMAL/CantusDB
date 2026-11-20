"""Reconcile Wikidata-only countries entered before their IDs were recognised."""

from django.db import migrations

from ._legacy_country_lookup import COUNTRY_BY_WIKIDATA, catalogue_ids
from ._institution_country_versions import convert_versions


def merged_fields(source, target):
    for key, value in source.authorities.items():
        if key in target.authorities and target.authorities[key] != value:
            raise ValueError(
                f"Countries {source.pk} and {target.pk} have conflicting {key} IDs. "
                "Correct the IDs before migrating."
            )
    authorities = target.authorities | source.authorities
    # Retain the stable row's display name and each distinct local spelling.
    aliases = target.aliases.splitlines()
    seen = {label.strip().casefold() for label in [target.name, *aliases]}
    for label in [source.name, *source.aliases.splitlines()]:
        normalized = label.strip().casefold()
        if normalized and normalized not in seen:
            aliases.append(label.strip())
            seen.add(normalized)
    if catalogue_ids([target.name, *aliases], authorities) != {target.pk}:
        raise ValueError(
            f"Check the names, aliases and authority IDs of countries {source.pk} and {target.pk} before merging them."
        )
    return {"aliases": "\n".join(aliases), "authorities": authorities}


def reconcile_countries(apps, schema_editor):
    db = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(db)
    institutions = apps.get_model("main_app", "Institution").objects.using(db)
    logs = (
        apps.get_model("admin", "LogEntry")
        .objects.using(db)
        .filter(content_type__app_label="main_app", content_type__model="country")
    )
    remap = {}
    by_pk = countries.in_bulk()
    for row in by_pk.values():
        new_pk = COUNTRY_BY_WIKIDATA.get(row.authorities.get("wikidata"))
        if new_pk is None:
            continue
        labels = [row.name, *row.aliases.splitlines()]
        if catalogue_ids(labels, row.authorities) != {new_pk} or (
            row.pk < 0 and row.pk != new_pk
        ):
            raise ValueError(
                f"Check the name, aliases and authority IDs of country {row.pk} "
                f"({row.name}) before migrating: they identify different countries."
            )
        if row.pk == new_pk:
            continue

        old_pk = row.pk
        target = by_pk.get(new_pk)
        if target is None:
            countries.filter(pk=old_pk).update(id=new_pk)
        institutions.filter(country_id=old_pk).update(country_id=new_pk)
        logs.filter(object_id=str(old_pk)).update(object_id=str(new_pk))
        if target is not None:
            # Release the old unique authority IDs before moving them to the stable row.
            fields = merged_fields(row, target)
            countries.filter(pk=old_pk).delete()
            countries.filter(pk=new_pk).update(**fields)
        remap[old_pk] = new_pk

    if remap:
        convert_versions(
            apps,
            db,
            lambda value: remap.get(int(value), value) if value is not None else None,
        )


class Migration(migrations.Migration):
    dependencies = [("main_app", "0049_country_authorities")]
    # Both schemas accept the repaired references. Rolling back keeps them valid.
    operations = [migrations.RunPython(reconcile_countries, migrations.RunPython.noop)]
