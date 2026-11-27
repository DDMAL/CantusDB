"""
List chants and sequences that still use a Cantus ID that Cantus Index has
merged into another one (issue #2197).

Cantus Index lists every merge at /json-merged-chants: an old Cantus ID, the
ID it was merged into, and the date. Some merges were later merged again
(A into B, then B into C), so each old ID is followed to the ID it ends up as.
A few old IDs were merged into more than one ID; those are listed separately,
since someone has to choose which one each chant should get.

Results are printed in the terminal, one block per old ID, with the sources
that use it. Pass --csv to also write one row per chant or sequence, for
sorting and sharing. Nothing is changed in the database.

Usage:
    python manage.py audit_merged_cantus_ids
    python manage.py audit_merged_cantus_ids --csv merged_ids.csv
    python manage.py audit_merged_cantus_ids --source 123610
"""

import argparse
import csv
from collections import defaultdict
from typing import Any, Optional

from django.core.management.base import BaseCommand, CommandError

from cantusindex import get_merged_cantus_ids

# the shared code also used by the weekly data checks (#2197)
from main_app.cantus_id_merges import (  # noqa: F401 (follow is used by tests)
    FETCH_TIMEOUT,
    Merge,
    follow,
    read_merges,
    records_using,
)


class Command(BaseCommand):
    help = (
        "List chants and sequences that still use a Cantus ID that Cantus Index "
        "has merged into another one. Changes nothing."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--source",
            type=int,
            help="Only check the chants and sequences of this source (its id).",
        )
        parser.add_argument(
            "--csv",
            metavar="PATH",
            help="Also write one row per chant or sequence to this CSV file.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        events = get_merged_cantus_ids(timeout=FETCH_TIMEOUT)
        if not events:
            raise CommandError(
                "Couldn't get the list of merged Cantus IDs from Cantus Index."
            )
        merges = read_merges(events)
        self.stdout.write(
            f"Cantus Index lists {len(events)} merges of {len(merges)} Cantus IDs."
        )

        rows = self._collect(merges, options["source"])
        self._report(rows, merges)
        if options["csv"]:
            self._write_csv(rows, options["csv"])

    def _collect(
        self, merges: dict[str, Merge], source_id: Optional[int]
    ) -> list[dict[str, Any]]:
        # the report lists sequences too, whatever the data checks do
        return records_using(merges, include_sequences=True, source_id=source_id)

    def _report(self, rows: list[dict[str, Any]], merges: dict[str, Merge]) -> None:
        if not rows:
            self.stdout.write(
                self.style.SUCCESS("No chants or sequences use a merged Cantus ID.")
            )
            return

        by_old_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            by_old_id[row["cantus_id"]].append(row)

        for heading, wanted in (
            ("Merged into one ID", lambda first: not first["note"]),
            ("Need a decision", lambda first: bool(first["note"])),
        ):
            old_ids = [
                old_id for old_id, group in by_old_id.items() if wanted(group[0])
            ]
            if not old_ids:
                continue
            count = sum(len(by_old_id[old_id]) for old_id in old_ids)
            self.stdout.write(
                f"\n{heading} ({len(old_ids)} Cantus ID(s), {count} record(s))"
            )
            for old_id in old_ids:
                group = by_old_id[old_id]
                first = group[0]
                target = first["note"] or f"→ {first['new_cantus_id']}"
                if not first["note"] and len(first["chain"].split(" → ")) > 2:
                    target += f" (via {first['chain']})"
                dates = ", ".join(sorted(set(merges[old_id].new.values())))
                self.stdout.write(f"  {old_id} {target}, merged {dates}")
                by_source: dict[tuple[int, str, bool], list[dict]] = defaultdict(list)
                for row in group:
                    by_source[
                        (row["source_id"], row["source"], row["published"])
                    ].append(row)
                for (source_id, name, published), records in by_source.items():
                    kinds = defaultdict(int)
                    for row in records:
                        kinds[row["kind"]] += 1
                    counts = ", ".join(
                        f"{n} {kind}{'s' if n > 1 else ''}"
                        for kind, n in sorted(kinds.items())
                    )
                    status = "" if published else ", unpublished"
                    self.stdout.write(
                        f"    source {source_id} ({name}{status}): {counts}"
                    )

        chants = sum(1 for row in rows if row["kind"] == "chant")
        sequences = len(rows) - chants
        self.stdout.write(
            f"\n{chants} chant(s) and {sequences} sequence(s) in "
            f"{len({row['source_id'] for row in rows})} source(s) use "
            f"{len(by_old_id)} merged Cantus ID(s). Nothing was changed."
        )

    def _write_csv(self, rows: list[dict[str, Any]], path: str) -> None:
        columns = [
            "kind",
            "id",
            "source_id",
            "source",
            "published",
            "folio",
            "order",
            "incipit",
            "cantus_id",
            "new_cantus_id",
            "chain",
            "merged",
            "note",
        ]
        with open(path, "w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(csv_file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        self.stdout.write(f"Wrote {len(rows)} row(s) to {path}.")
