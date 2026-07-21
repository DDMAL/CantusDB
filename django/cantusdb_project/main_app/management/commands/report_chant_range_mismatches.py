import csv
import sys
from collections import Counter
from contextlib import contextmanager
from typing import Any, Iterator, Optional, TextIO, Union

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q

from main_app.models import Chant, Sequence
from main_app.signals import generate_chant_range

CSV_HEADER = [
    "model",
    "record_id",
    "source_id",
    "folio",
    "stored_range",
    "derived_range",
    "difference_type",
]

# The models this report covers, paired with the label written to the CSV. Kept
# in step with populate_chant_ranges so this report can serve as that command's
# backup before an --overwrite run.
TARGET_MODELS: list[tuple[str, Union[type[Chant], type[Sequence]]]] = [
    ("chant", Chant),
    ("sequence", Sequence),
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
        "Read-only report of chants and sequences whose stored chant_range "
        "disagrees with the range derived from their volpiano. Each row is tagged "
        "with a difference_type (case / formatting / pitch) so proofreaders can "
        "filter; 'pitch' rows are the genuine ambitus disagreements. Mutates "
        "nothing (see #2081 / #1176)."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Path to write the CSV report to (defaults to stdout).",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        output_path: Optional[str] = options["output"]

        counts: Counter[str] = Counter()
        with open_output(output_path) as output:
            writer = csv.writer(output)
            writer.writerow(CSV_HEADER)
            for label, model in TARGET_MODELS:
                # Only the fields this report reads are loaded; records carry
                # large text columns (full texts, search_vector) that would
                # otherwise be fetched for every row. Safe because this command
                # never writes.
                records = (
                    model.objects.filter(Q(volpiano__isnull=False) & ~Q(volpiano=""))
                    .exclude(Q(chant_range__isnull=True) | Q(chant_range=""))
                    .only("id", "source", "folio", "chant_range", "volpiano")
                )
                for record in records.iterator(chunk_size=500):
                    derived = generate_chant_range(record.volpiano)
                    if derived and derived != record.chant_range:
                        difference_type = classify_difference(
                            record.chant_range, derived
                        )
                        counts[difference_type] += 1
                        writer.writerow(
                            [
                                label,
                                record.pk,
                                # .source_id (not .source.pk) so reading the FK
                                # never triggers a per-row query. django-stubs
                                # doesn't model the implicit "<fk>_id" attribute,
                                # hence the ignore.
                                record.source_id,  # type: ignore[union-attr]
                                record.folio,
                                record.chant_range,
                                derived,
                                difference_type,
                            ]
                        )

        # Summary goes to stderr so it never pollutes a CSV streamed to stdout.
        # Written unstyled: OutputWrapper already applies its own style_func to
        # stderr, which would wrap (not replace) any style applied here.
        breakdown = ", ".join(f"{n} {t}" for t, n in sorted(counts.items()))
        self.stderr.write(
            f"Found {sum(counts.values())} mismatched records"
            + (f" ({breakdown})." if breakdown else ".")
        )
