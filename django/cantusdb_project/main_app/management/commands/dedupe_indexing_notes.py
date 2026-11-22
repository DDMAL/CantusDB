"""
Collapse indexing notes that are one note repeated (issue #2234).

Some chants' indexing notes were stored several times over, joined by " | ",
e.g. "ams186 | ams186 | ams186". This command replaces each of those with a
single copy. Notes whose parts differ are left alone, including notes where one
part is a shorter or older version of another; those are reviewed by hand.

Each changed chant gets two revisions, one with the note before the change and
one after, so the old note can be restored from the admin history. The new
notes are written with `bulk_update`, which skips the chant save signals: they
would recount every affected source's chants and bump its "last modified" date
for an edit no user made (issue #2304).

Usage:
    python manage.py dedupe_indexing_notes --dry-run --csv notes.csv
    python manage.py dedupe_indexing_notes
"""

import argparse
import csv
from typing import Any, Optional

import reversion  # type: ignore[import-untyped]
from django.core.management.base import BaseCommand
from django.db import transaction

from main_app.models import Chant

SEPARATOR = " | "


def collapse_repeated_note(note: Optional[str]) -> Optional[str]:
    """
    Return the single note if `note` is one note repeated with " | ",
    otherwise None. A blank note repeated (e.g. non-breaking spaces,
    "\\xa0 | \\xa0") becomes an empty note.
    """
    if not note or SEPARATOR not in note:
        return None
    parts = [part.strip() for part in note.split(SEPARATOR)]
    if any(part != parts[0] for part in parts):
        return None
    return parts[0]


class Command(BaseCommand):
    help = (
        "Collapse indexing notes that are one note repeated with ' | ' "
        "(issue #2234). Use --dry-run to preview without writing."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the changes without writing any data.",
        )
        parser.add_argument(
            "--csv",
            metavar="PATH",
            help="Write every change (chant, source, old note, new note) to a CSV file.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]

        with transaction.atomic():
            chants = Chant.objects.filter(indexing_notes__contains=SEPARATOR)
            if not dry_run:
                # Lock the rows so an edit made while this runs isn't overwritten.
                chants = chants.select_for_update()
            changes = []
            for chant in chants.order_by("pk"):
                new_note = collapse_repeated_note(chant.indexing_notes)
                if new_note is not None:
                    changes.append((chant, chant.indexing_notes, new_note))

            if options["csv"]:
                self._write_csv(options["csv"], changes)
            if changes and not dry_run:
                self._apply(changes)

        sources = {chant.source_id for chant, _, _ in changes}
        verb = "Would change" if dry_run else "Changed"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {len(changes)} chant(s) in {len(sources)} source(s)."
            )
        )

    def _write_csv(self, path: str, changes: list[tuple[Chant, str, str]]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as file:
            writer = csv.writer(file)
            writer.writerow(["chant_id", "source_id", "old_note", "new_note"])
            for chant, old_note, new_note in changes:
                writer.writerow([chant.pk, chant.source_id, old_note, new_note])

    def _apply(self, changes: list[tuple[Chant, str, str]]) -> None:
        with reversion.create_revision():
            reversion.set_comment("dedupe_indexing_notes: note before (issue #2234)")
            for chant, _, _ in changes:
                reversion.add_to_revision(chant)

        with reversion.create_revision():
            reversion.set_comment(
                "dedupe_indexing_notes: repeated note collapsed (issue #2234)"
            )
            for chant, _, new_note in changes:
                chant.indexing_notes = new_note
                reversion.add_to_revision(chant)
            Chant.objects.bulk_update(
                [chant for chant, _, _ in changes],
                ["indexing_notes"],
                batch_size=500,
            )
