import csv
import sys
from contextlib import contextmanager
from typing import Any, Iterator, Optional, TextIO

from django.core.management.base import BaseCommand
from django.db.models import Q

from main_app.models import Chant
from main_app.signals import generate_chant_range, generate_volpiano_notes

CSV_HEADER = ["chant_id", "source_id", "folio", "stored_range", "derived_range"]


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
        "range derived from their volpiano. Mutates nothing; hand the CSV to "
        "proofreaders to validate through the normal edit flow (see #2081 / #1176)."
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

        mismatches = 0
        with open_output(output_path) as output:
            writer = csv.writer(output)
            writer.writerow(CSV_HEADER)
            for chant in chants.iterator(chunk_size=500):
                derived = generate_chant_range(generate_volpiano_notes(chant.volpiano))
                if derived and derived != chant.chant_range:
                    mismatches += 1
                    writer.writerow(
                        [
                            chant.id,
                            chant.source_id,
                            chant.folio,
                            chant.chant_range,
                            derived,
                        ]
                    )

        # Summary goes to stderr so it never pollutes a CSV streamed to stdout.
        self.stderr.write(self.style.SUCCESS(f"Found {mismatches} mismatched chants."))
