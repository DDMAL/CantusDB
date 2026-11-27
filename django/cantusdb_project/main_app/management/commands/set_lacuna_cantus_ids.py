"""
Give placeholder chants for manuscript gaps the Cantus ID "LACUNA" (issue #2264).

Placeholders for gaps in a manuscript have the text LACUNA and a blank Cantus
ID, so they show up in the blank-Cantus-ID report. The rule agreed in #2264:
a chant whose incipit is exactly "LACUNA" (in capitals, so a Latin sentence
using the word doesn't match) and whose Cantus ID is blank gets the Cantus ID
"LACUNA". Chants whose Cantus ID is already "lacuna" in another case are
changed to "LACUNA" too (agreed in #2264).

The report also lists the cases the rule leaves alone, for review:
- the text is LACUNA but the chant has a real Cantus ID;
- the incipit mentions a lacuna but isn't exactly LACUNA;
- chants in the [Lacuna] feast whose text isn't LACUNA (real chants).

Each changed chant gets a "before" and an "after" revision in its history, so
it can be restored on its own. Only the Cantus ID is written: the chant's and
source's last-modified dates and people stay as they were. "LACUNA" is in
settings.RESERVED_CANTUS_IDS, so these chants don't move from the blank-ID
report to the not-in-Cantus-Index one.

Usage:
    python manage.py set_lacuna_cantus_ids --dry-run      # report only
    python manage.py set_lacuna_cantus_ids --dry-run --csv lacuna.csv
    python manage.py set_lacuna_cantus_ids
"""

import argparse
import csv
from collections import Counter, defaultdict
from typing import Any

import reversion  # type: ignore[import-untyped]
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q

from main_app.models import Chant, Source

LACUNA = "LACUNA"
LACUNA_FEAST = "[Lacuna]"

SET = "set to LACUNA"
CHANGE_CASE = "change case to LACUNA"
ALREADY = "already LACUNA"
HAS_ID = "leave: has a Cantus ID"
NOT_EXACT = "leave: not exactly LACUNA"
REAL_CHANT = "leave: real chant in the [Lacuna] feast"
ORDER = [SET, CHANGE_CASE, HAS_ID, NOT_EXACT, ALREADY, REAL_CHANT]


def classify(chant: dict[str, Any]) -> tuple[str, str]:
    """What the rule does with a chant, and a note for the report."""
    cantus_id = (chant["cantus_id"] or "").strip()
    if chant["incipit"] == LACUNA:
        if not cantus_id:
            manuscript_text = (chant["manuscript_full_text"] or "").strip()
            if manuscript_text and manuscript_text != LACUNA:
                return SET, f"manuscript text is {manuscript_text!r}, not LACUNA"
            return SET, ""
        if cantus_id == LACUNA:
            return ALREADY, ""
        if cantus_id.upper() == LACUNA:
            return CHANGE_CASE, f"Cantus ID is {cantus_id!r}"
        return HAS_ID, f"text is LACUNA but Cantus ID is {cantus_id}"
    if "lacuna" in (chant["incipit"] or "").lower():
        return NOT_EXACT, f"incipit is {chant['incipit']!r}"
    return REAL_CHANT, ""


class Command(BaseCommand):
    help = (
        'Give placeholder chants for manuscript gaps the Cantus ID "LACUNA" '
        "(#2264). Use --dry-run to list the changes without writing."
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
            help="Also write one row per chant to this CSV file.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        with transaction.atomic():
            rows = self._collect(lock=not dry_run)
            self._report(rows, dry_run)
            if options["csv"]:
                self._write_csv(rows, options["csv"])
            if not dry_run:
                self._apply(rows)

    def _apply(self, rows: list[dict[str, Any]]) -> None:
        ids = [row["id"] for row in rows if row["action"] in (SET, CHANGE_CASE)]
        chants = list(Chant.objects.filter(id__in=ids))
        # One pair of revisions per chant: restoring a chant from its history
        # reverts its whole revision, so a shared one would revert them all.
        for chant in chants:
            with reversion.create_revision():
                reversion.set_comment("set_lacuna_cantus_ids: before (issue #2264)")
                reversion.add_to_revision(chant)
            chant.cantus_id = LACUNA
            with reversion.create_revision():
                reversion.set_comment(
                    "set_lacuna_cantus_ids: Cantus ID set to LACUNA (issue #2264)"
                )
                reversion.add_to_revision(chant)
        # bulk_update writes only the Cantus ID and skips save(), so the
        # chants' and sources' last-modified dates are left alone.
        Chant.objects.bulk_update(chants, ["cantus_id"], batch_size=500)
        self.stdout.write(
            self.style.SUCCESS(f"Set the Cantus ID LACUNA on {len(chants)} chant(s).")
        )

    def _collect(self, lock: bool = False) -> list[dict[str, Any]]:
        chants = Chant.objects.filter(
            Q(incipit__icontains="lacuna") | Q(feast__name=LACUNA_FEAST)
        )
        if lock:
            # Lock the rows so an edit made while this runs isn't overwritten.
            chants = chants.select_for_update(of=("self",))
        chants = chants.values(
            "id",
            "source_id",
            "folio",
            "c_sequence",
            "feast__name",
            "incipit",
            "manuscript_full_text",
            "manuscript_full_text_std_spelling",
            "cantus_id",
        )
        rows = []
        for chant in chants:
            action, note = classify(chant)
            rows.append({**chant, "action": action, "note": note})

        sources = Source.objects.select_related("holding_institution").in_bulk(
            {row["source_id"] for row in rows}
        )
        for row in rows:
            source = sources.get(row["source_id"])
            row["source"] = source.short_heading if source else ""
            row["published"] = bool(source and source.published)
        rows.sort(
            key=lambda row: (
                ORDER.index(row["action"]),
                row["source"],
                row["folio"] or "",
                row["c_sequence"] or 0,
            )
        )
        return rows

    def _report(self, rows: list[dict[str, Any]], dry_run: bool) -> None:
        by_action: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_action[row["action"]].append(row)

        for action in ORDER:
            group = by_action.get(action)
            if not group:
                continue
            sources = {row["source_id"] for row in group}
            published = sum(row["published"] for row in group)
            self.stdout.write(
                f"\n{action}: {len(group)} chant(s) in {len(sources)} source(s), "
                f"{published} in published sources"
            )
            if action == SET:
                feasts = Counter(row["feast__name"] or "(no feast)" for row in group)
                self.stdout.write(
                    "  feasts: "
                    + ", ".join(f"{name} {n}" for name, n in feasts.most_common(6))
                )
                for row in group:
                    if row["note"]:
                        self.stdout.write(f"  check: {self._describe(row)}")
            elif action != REAL_CHANT:
                for row in group:
                    self.stdout.write(f"  {self._describe(row)}")

        count = len(by_action.get(SET, [])) + len(by_action.get(CHANGE_CASE, []))
        if dry_run:
            self.stdout.write(
                f"\n{count} chant(s) would get the Cantus ID LACUNA. "
                "Nothing was changed (dry run)."
            )

    @staticmethod
    def _describe(row: dict[str, Any]) -> str:
        return (
            f"chant {row['id']} in {row['source']} ({row['source_id']}) "
            f"f. {row['folio'] or '?'}: {row['note'] or row['incipit']}"
        )

    def _write_csv(self, rows: list[dict[str, Any]], path: str) -> None:
        columns = [
            "action",
            "note",
            "id",
            "source_id",
            "source",
            "published",
            "folio",
            "c_sequence",
            "feast__name",
            "incipit",
            "manuscript_full_text",
            "manuscript_full_text_std_spelling",
            "cantus_id",
        ]
        with open(path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(f"Wrote {len(rows)} row(s) to {path}.")
