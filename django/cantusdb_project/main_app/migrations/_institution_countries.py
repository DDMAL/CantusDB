"""Convert existing institution records between country text and country IDs."""

from collections import defaultdict

from ._legacy_country_lookup import IDS_BY_LABEL, NAMES
from ._institution_country_versions import convert_versions

NOT_RECORDED, UNKNOWN = -1, -2


def from_text(
    apps,
    schema_editor,
    *,
    names=NAMES,
    by_label=IDS_BY_LABEL,
    not_recorded=NOT_RECORDED,
    unknown=UNKNOWN
):
    db = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(db)
    institutions = apps.get_model("main_app", "Institution").objects.using(db)
    ids = {"": not_recorded}
    for pk, name, alias in (
        (not_recorded, "Not recorded", "[No Country]"),
        (unknown, "Unknown", "[Unknown Country]"),
    ):
        countries.create(pk=pk, name=name, aliases=alias)
        ids[name.casefold()] = ids[alias.casefold()] = pk

    represented = {}
    spellings = defaultdict(list)

    def country_id(value, *, historical=False):
        text = (value or "").strip()
        key = text.casefold()
        if key in ids:
            return ids[key]
        pk = by_label.get(key)
        if pk is None:
            if historical:
                return unknown
            pk = countries.create(name=text).pk
        else:
            if pk not in represented:
                represented[pk] = countries.create(pk=pk, name=names[pk])
            if key != names[pk].casefold():
                spellings[pk].append(text)
        ids[key] = pk
        return pk

    values = (
        institutions.order_by("country_text")
        .values_list("country_text", flat=True)
        .distinct()
    )
    for value in list(values):
        institutions.filter(country_text=value).update(country_id=country_id(value))
    convert_versions(apps, db, lambda value: country_id(value, historical=True))
    for pk, aliases in spellings.items():
        represented[pk].aliases = "\n".join(aliases)
    countries.bulk_update([represented[pk] for pk in spellings], ["aliases"])


def to_text(apps, schema_editor, *, not_recorded=NOT_RECORDED):
    db = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(db)
    institutions = apps.get_model("main_app", "Institution").objects.using(db)
    names = dict(countries.values_list("pk", "name"))
    names[not_recorded] = "[No Country]"
    for pk, name in names.items():
        institutions.filter(country_id=pk).update(country_text=name)
    convert_versions(apps, db, lambda value: names[int(value)])
