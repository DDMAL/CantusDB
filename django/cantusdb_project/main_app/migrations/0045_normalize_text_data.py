"""Normalize the text fields reported in #1585 before adding NOT NULL.

Run with application writers stopped and a database backup available. Reversing
this migration retains normalized data: original NULLs and whitespace cannot be
inferred. See docs/text-field-cleanup.md for deployment and recovery.
"""

import re

from django.apps.registry import Apps
from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.models import Count, Q

BATCH_SIZE = 500
CHANT_FIELDS = (
    "manuscript_full_text",
    "manuscript_full_text_std_spelling",
    "manuscript_syllabized_full_text",
    "image_link",
    "indexing_notes",
    "volpiano",
    "volpiano_notes",
    "volpiano_intervals",
)
SOURCE_FIELDS = ("description", "selected_bibliography", "summary")


def melody_fields(volpiano: str) -> tuple[str, str]:
    # Freeze the current derivation here, rather than importing application
    # signals whose behavior may change before this migration is run again.
    notes = volpiano.lower().replace(")", "9")
    for character in "-1234567?. yiz":
        notes = notes.replace(character, "")
    notes = re.sub(r"(.)\1+", r"\1", notes)
    pitches = [ord(note) for note in notes.replace("9", "`")]
    pitches = [pitch - 1 if pitch >= 106 else pitch for pitch in pitches]
    intervals = "".join(str(right - left) for left, right in zip(pitches, pitches[1:]))
    return notes, intervals


def normalize_text_data(apps: Apps, schema_editor: BaseDatabaseSchemaEditor) -> None:
    alias = schema_editor.connection.alias
    for model_name in ("Chant", "Sequence", "Source"):
        model = apps.get_model("main_app", model_name)
        fields = SOURCE_FIELDS if model_name == "Source" else CHANT_FIELDS
        objects = model.objects.using(alias)
        last_pk = None
        while True:
            remaining = objects if last_pk is None else objects.filter(pk__gt=last_pk)
            batch = list(remaining.order_by("pk").only("pk", *fields)[:BATCH_SIZE])
            if not batch:
                break
            changed = []
            for obj in batch:
                before = {field: getattr(obj, field) for field in fields}
                for field, value in before.items():
                    trimmed = value.strip() if value else ""
                    # Populated notes/rich text can contain significant
                    # indentation and Markdown hard-break spaces.
                    preserve_spacing = (
                        model_name == "Source" or field == "indexing_notes"
                    )
                    normalized = value if preserve_spacing and trimmed else trimmed
                    setattr(obj, field, normalized)
                if model_name != "Source":
                    if not obj.volpiano:
                        obj.volpiano_notes = ""
                        obj.volpiano_intervals = ""
                    elif obj.volpiano != before["volpiano"]:
                        obj.volpiano_notes, obj.volpiano_intervals = melody_fields(
                            obj.volpiano
                        )
                if any(getattr(obj, field) != value for field, value in before.items()):
                    changed.append(obj)
            if changed:
                # Historical models/bulk_update deliberately avoid save signals:
                # do not regenerate curated incipits or change editorial dates.
                objects.bulk_update(changed, fields, batch_size=BATCH_SIZE)
            last_pk = batch[-1].pk

    # Whitespace-only melodies no longer count. Follow the existing convention:
    # this source counter counts Chant melodies, not Sequence melodies.
    source = apps.get_model("main_app", "Source")
    sources = source.objects.using(alias).annotate(
        actual_melodies=Count("chant", filter=Q(chant__volpiano__gt=""))
    )
    for obj in sources.only("pk", "number_of_melodies").iterator(chunk_size=BATCH_SIZE):
        if obj.number_of_melodies != obj.actual_melodies:
            source.objects.using(alias).filter(pk=obj.pk).update(
                number_of_melodies=obj.actual_melodies
            )


class Migration(migrations.Migration):
    dependencies = [("main_app", "0044_alter_source_source_completeness")]

    operations = [
        # Undoing the schema constraint is safe while retaining canonical data.
        # Exact data recovery requires the pre-migration backup.
        migrations.RunPython(normalize_text_data, migrations.RunPython.noop),
    ]
