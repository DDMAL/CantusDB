from typing import Any, Union

from django.core.management.base import BaseCommand, CommandParser
from django.db.models import Q

from main_app.models import Chant, Sequence
from main_app.signals import generate_chant_range

# The models this command backfills, paired with the label used to report them.
# chant_range and volpiano both live on BaseChant, so sequences carry them too.
TARGET_MODELS: list[tuple[str, Union[type[Chant], type[Sequence]]]] = [
    ("chants", Chant),
    ("sequences", Sequence),
]


class Command(BaseCommand):
    help = (
        "Backfill chant_range from volpiano for chants and sequences that have "
        "volpiano. By default only blank ranges are filled; pass --overwrite to "
        "recompute ranges that disagree with their melody (see #2081 / #1176). "
        "Writes directly with .update() to avoid re-firing the full post_save "
        "cascade."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count the records that would be updated without writing anything.",
        )
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help=(
                "Also recompute ranges that already hold a value, replacing any "
                "that disagree with the melody. These writes bypass the version "
                "history and cannot be undone: run report_chant_range_mismatches "
                "first and keep its CSV as a backup."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        overwrite: bool = options["overwrite"]

        if dry_run:
            self.stdout.write("(Dry-run mode: no database changes will be made.)")
        elif overwrite:
            self.stdout.write(
                self.style.WARNING(
                    "Overwrite mode: stored ranges that disagree with their "
                    "volpiano will be replaced. This cannot be undone."
                )
            )

        counts = {
            label: self.backfill(model, dry_run=dry_run, overwrite=overwrite)
            for label, model in TARGET_MODELS
        }

        verb = "would be updated" if dry_run else "updated"
        breakdown = ", ".join(f"{count} {label}" for label, count in counts.items())
        self.stdout.write(self.style.SUCCESS(f"Success! {breakdown} {verb}."))

    def backfill(
        self,
        model: Union[type[Chant], type[Sequence]],
        *,
        dry_run: bool,
        overwrite: bool,
    ) -> int:
        """Recompute chant_range for one model, returning the number of rows written."""
        # Only the fields this command reads are loaded; records carry large text
        # columns (full texts, search_vector) that would otherwise be fetched for
        # every row. Safe because we never call save() on these instances — the
        # write below goes through a separate .update() queryset.
        records = model.objects.filter(
            Q(volpiano__isnull=False) & ~Q(volpiano="")
        ).only("id", "volpiano", "chant_range")
        if not overwrite:
            records = records.filter(Q(chant_range__isnull=True) | Q(chant_range=""))

        updated = 0
        for record in records.iterator(chunk_size=500):
            chant_range = generate_chant_range(record.volpiano)
            # Skipping rows that already hold the derived value keeps the reported
            # count honest and, under --overwrite, avoids rewriting most of the
            # table to no effect.
            if not chant_range or chant_range == record.chant_range:
                continue
            if dry_run:
                updated += 1
                continue
            write = model.objects.filter(pk=record.pk)
            if not overwrite:
                # Re-check the blank condition at the DB level inside the write. This
                # makes it impossible to clobber a value written between our read and
                # our write, and .update() returns the number of rows it actually
                # touched — so the count never overstates what was written.
                write = write.filter(Q(chant_range__isnull=True) | Q(chant_range=""))
            updated += write.update(chant_range=chant_range)
        return updated
