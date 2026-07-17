from typing import Any

from django.core.management.base import BaseCommand
from django.db.models import Q

from main_app.models import Chant
from main_app.signals import generate_chant_range, generate_volpiano_notes


class Command(BaseCommand):
    help = (
        "Backfill chant_range from volpiano for chants that have volpiano but a "
        "blank chant_range. Existing ranges are never overwritten (see #2081 / "
        "#1176). Writes directly with .update() to avoid re-firing the full "
        "on_chant_save cascade."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count the chants that would be updated without writing anything.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        if dry_run:
            self.stdout.write("(Dry-run mode: no database changes will be made.)")

        chants = Chant.objects.filter(
            Q(volpiano__isnull=False) & ~Q(volpiano="")
        ).filter(Q(chant_range__isnull=True) | Q(chant_range=""))

        updated = 0
        for chant in chants.iterator(chunk_size=500):
            chant_range = generate_chant_range(generate_volpiano_notes(chant.volpiano))
            if not chant_range:
                continue
            if not dry_run:
                Chant.objects.filter(id=chant.id).update(chant_range=chant_range)
            updated += 1

        verb = "would be updated" if dry_run else "updated"
        self.stdout.write(self.style.SUCCESS(f"Success! {updated} chants {verb}."))
