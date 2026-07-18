import csv
import sys
from collections import Counter
from contextlib import contextmanager
from typing import Any, Iterator, Optional, TextIO

from django.core.management.base import BaseCommand
from django.db.models import Q

from main_app.models import Chant
from main_app.signals import generate_chant_range, generate_volpiano_notes

CSV_HEADER = [
    "chant_id",
    "source_id",
    "folio",
    "stored_range",
    "derived_range",
    "difference_type",
]


def classify_difference(stored: str, derived: str) -> str:
    """Categorize a stored-vs-derived range mismatch for proofreader triage.

    - ``case``: same pitches, but the stored range marks an extreme note as a
      liquescent (uppercase) where the derived value is plain lowercase.
    - ``formatting``: same pitches, but the stored range is malformed, e.g. a
      missing dash ("1c-g-4" vs "1-c-g-4").
    - ``pitch``: the ambitus itself disagrees — the genuine signal to check.
    """
    if stored.lower() == derived.lower():
        return "case"
    if stored.lower().replace("-", "") == derived.lower().replace("-", ""):
        return "formatting"
    return "pitch"


@contextmanager
def open_output(path: Optional[str]) -> Iterator[TextIO]:
    if path is None:
        yield sys.stdout
        return
    with open(path, "w", newline="", encoding="utf-8") as file:
        yield file


class Command(BaseCommand):
    help = (
        "Read-only report of chants whose stored chant_range disagrees with the "
        "range derived from their volpiano. Each row is tagged with a "
        "difference_type (case / formatting / pitch) so proofreaders can filter; "
        "'pitch' rows are the genuine ambitus disagreements. Mutates nothing "
        "(see #2081 / #1176)."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Path to write the CSV report to (defaults to stdout).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        output_path: Optional[str] = options["output"]

        chants = Chant.objects.filter(
            Q(volpiano__isnull=False) & ~Q(volpiano="")
        ).exclude(Q(chant_range__isnull=True) | Q(chant_range=""))

        counts: Counter = Counter()
        with open_output(output_path) as output:
            writer = csv.writer(output)
            writer.writerow(CSV_HEADER)
            for chant in chants.iterator(chunk_size=500):
                derived = generate_chant_range(generate_volpiano_notes(chant.volpiano))
                if derived and derived != chant.chant_range:
                    difference_type = classify_difference(chant.chant_range, derived)
                    counts[difference_type] += 1
                    writer.writerow(
                        [
                            chant.id,
                            chant.source_id,
                            chant.folio,
                            chant.chant_range,
                            derived,
                            difference_type,
                        ]
                    )

        # Summary goes to stderr so it never pollutes a CSV streamed to stdout.
        breakdown = ", ".join(f"{n} {t}" for t, n in sorted(counts.items()))
        self.stderr.write(
            self.style.SUCCESS(
                f"Found {sum(counts.values())} mismatched chants"
                + (f" ({breakdown})." if breakdown else ".")
            )
        )
