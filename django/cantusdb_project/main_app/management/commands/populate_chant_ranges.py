from typing import Any, Union

import reversion
from django.core.management.base import BaseCommand, CommandParser
from django.db import transaction
from django.db.models import Q

from main_app.chant_range import generate_chant_range
from main_app.models import Chant, Sequence

TARGET_MODELS: list[tuple[str, Union[type[Chant], type[Sequence]]]] = [
    ("chants", Chant),
    ("sequences", Sequence),
]


class Command(BaseCommand):
    help = (
        "Backfill chant_range from volpiano for chants and sequences. By default "
        "only blank ranges are filled; --overwrite also repairs mismatches. "
        "Each changed record gets before/after revisions labelled "
        "populate_chant_ranges. Review report_chant_range_mismatches before "
        "using --overwrite."
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
            help="Also replace existing ranges that disagree with their melody.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        overwrite: bool = options["overwrite"]
        if dry_run:
            self.stdout.write("(Dry-run mode: no database changes will be made.)")
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
        """Repair candidates using their current melody and retain revision history."""
        records = model.objects.filter(
            Q(volpiano__isnull=False) & ~Q(volpiano="")
        ).only("id", "volpiano", "chant_range")
        if not overwrite:
            records = records.filter(
                Q(chant_range__isnull=True) | Q(chant_range__regex=r"^\s*$")
            )

        updated = 0
        for candidate in records.iterator(chunk_size=500):
            derived = generate_chant_range(candidate.volpiano)
            if not derived or derived == candidate.chant_range:
                continue
            if dry_run:
                updated += 1
                continue
            # An editor may have changed the melody or range since the candidate
            # query ran. Lock and reread the row before deriving or recording it.
            with transaction.atomic():
                record = (
                    model.objects.select_for_update().filter(pk=candidate.pk).first()
                )
                if record is None or (
                    (record.chant_range or "").strip() and not overwrite
                ):
                    continue
                derived = generate_chant_range(record.volpiano or "")
                if not derived or derived == record.chant_range:
                    continue
                with reversion.create_revision(manage_manually=True):
                    reversion.set_comment("populate_chant_ranges: before range update")
                    reversion.add_to_revision(record)
                # Avoid unrelated post_save cascades and preserve all other
                # fields, including timestamps. Both versions are explicitly
                # recorded inside the same transaction as this update.
                model.objects.filter(pk=record.pk).update(chant_range=derived)
                record.chant_range = derived
                with reversion.create_revision(manage_manually=True):
                    reversion.set_comment("populate_chant_ranges: derived range")
                    reversion.add_to_revision(record)
                updated += 1
        return updated
