"""Reserve the catalogue's IDs and upgrade databases using the earlier IDs."""

from django.db import models

from ._institution_countries import from_text, to_text
from ._institution_country_versions import convert_versions
from ._legacy_country_lookup import IDS_BY_LABEL, NAMES

NOT_RECORDED, UNKNOWN, FIRST_LOCAL_ID = 37, 38, 39
LEGACY_TO_POSITIVE = {pk: -pk - 100 for pk in NAMES} | {-1: NOT_RECORDED, -2: UNKNOWN}


def reserve_sequence(schema_editor, first_id, highest_pk=0):
    with schema_editor.connection.cursor() as cursor:
        # The regclass text is PostgreSQL's quoted SQL name, including schema
        # when needed. Preserve allocations made for records since deleted.
        cursor.execute(
            "SELECT pg_get_serial_sequence('main_app_country', 'id')::regclass::text"
        )
        sequence = cursor.fetchone()[0]
        cursor.execute(f"SELECT last_value, is_called FROM {sequence}")
        last, called = cursor.fetchone()
        start = max(first_id, highest_pk + 1, last + int(called))
        cursor.execute(
            f"ALTER SEQUENCE {sequence} START WITH {first_id} RESTART WITH {start}"
        )


def from_text_positive(apps, schema_editor):
    reserve_sequence(schema_editor, FIRST_LOCAL_ID)
    from_text(
        apps,
        schema_editor,
        names={LEGACY_TO_POSITIVE[pk]: name for pk, name in NAMES.items()},
        by_label={label: LEGACY_TO_POSITIVE[pk] for label, pk in IDS_BY_LABEL.items()},
        not_recorded=NOT_RECORDED,
        unknown=UNKNOWN,
    )


def to_text_positive(apps, schema_editor):
    to_text(apps, schema_editor, not_recorded=NOT_RECORDED)


def replace_values(rows, field, mapping):
    if mapping:
        replacements = [
            models.When(**{field: old}, then=models.Value(new))
            for old, new in mapping.items()
        ]
        rows.filter(**{f"{field}__in": mapping}).update(
            **{field: models.Case(*replacements)}
        )


def rekey(apps, schema_editor, *, forwards):
    db = schema_editor.connection.alias
    countries = apps.get_model("main_app", "Country").objects.using(db)
    institutions = apps.get_model("main_app", "Institution").objects.using(db)
    logs = (
        apps.get_model("admin", "LogEntry")
        .objects.using(db)
        .filter(content_type__app_label="main_app", content_type__model="country")
    )
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("LOCK TABLE main_app_country IN ACCESS EXCLUSIVE MODE")
    existing = set(countries.values_list("pk", flat=True))
    legacy = LEGACY_TO_POSITIVE
    if forwards:
        # Older databases could allocate any positive ID to a local country,
        # including a slot for a catalogue entry that has not been loaded yet.
        reserved = set(legacy.values())
        displaced = sorted(
            pk for pk in existing if pk in reserved or (pk <= 0 and pk not in legacy)
        )
        reserve_sequence(schema_editor, FIRST_LOCAL_ID, max(existing | reserved))
        moved = {}
        if displaced:
            with schema_editor.connection.cursor() as cursor:
                cursor.execute(
                    "SELECT nextval(pg_get_serial_sequence('main_app_country', 'id')) "
                    "FROM generate_series(1, %s)",
                    [len(displaced)],
                )
                moved = {
                    pk: new
                    for pk, (new,) in zip(displaced, cursor.fetchall(), strict=True)
                }
        fixed = {pk: legacy[pk] for pk in existing & legacy.keys()}
    else:
        moved = {}
        fixed = {new: old for old, new in legacy.items() if new in existing}

    # Free occupied slots first. Rewrite references in one pass so an old
    # local ID and a catalogue ID moving into its slot cannot be confused.
    replace_values(countries, "id", moved)
    replace_values(countries, "id", fixed)
    mapping = moved | fixed
    if mapping:
        replace_values(institutions, "country_id", mapping)
        replace_values(logs, "object_id", {str(k): str(v) for k, v in mapping.items()})
        convert_versions(
            apps,
            db,
            lambda value: mapping.get(int(value), value) if value is not None else None,
        )
    if not forwards:
        highest = max(existing - fixed.keys(), default=0)
        reserve_sequence(schema_editor, 1, highest)
    # Complete the FK checks before the migration adds the positive-ID constraint.
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


def use_positive_ids(apps, schema_editor):
    rekey(apps, schema_editor, forwards=True)


def restore_legacy_ids(apps, schema_editor):
    rekey(apps, schema_editor, forwards=False)
