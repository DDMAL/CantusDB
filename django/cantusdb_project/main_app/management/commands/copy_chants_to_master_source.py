import argparse
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
import reversion  # type: ignore[import-untyped]

from main_app.models import Chant, Source

MASTER_SOURCE_ID = 1000289
FOLIO_RE = re.compile(r"^K\d{3}[A-Za-z]?$")


class Command(BaseCommand):
    help = "Copy ~710 chants from student-work sources into the Kaiatonsera master source (issue #2038)."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print per-group counts and sanity checks without writing any data.",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]

        try:
            master_source = Source.objects.get(id=MASTER_SOURCE_ID)
        except Source.DoesNotExist as e:
            raise CommandError(f"Master source {MASTER_SOURCE_ID} not found.") from e

        groups = [
            (
                "Group 1: source 1000260, K005–K028 (~200)",
                Chant.objects.filter(
                    source_id=1000260,
                    folio__gte="K005",
                    folio__lt="K029",
                ).order_by("folio", "c_sequence"),
            ),
            (
                "Group 2: source 1000208, K039–K053 (~155)",
                Chant.objects.filter(
                    source_id=1000208,
                    folio__gte="K039",
                    folio__lt="K054",
                ).order_by("folio", "c_sequence"),
            ),
            (
                "Group 3: source 1000260, K053(seq≥5)–K067 (~140)",
                Chant.objects.filter(source_id=1000260)
                .filter(
                    Q(folio="K053", c_sequence__gte=5)
                    | Q(folio__gt="K053", folio__lt="K068")
                )
                .order_by("folio", "c_sequence"),
            ),
            (
                "Group 4: source 1000260, K082–K090 (~80)",
                Chant.objects.filter(
                    source_id=1000260,
                    folio__gte="K082",
                    folio__lt="K091",
                ).order_by("folio", "c_sequence"),
            ),
            (
                "Group 5: source 1000208, K090(seq≥7)–K108 (~135)",
                Chant.objects.filter(source_id=1000208)
                .filter(
                    Q(folio="K090", c_sequence__gte=7)
                    | Q(folio__gt="K090", folio__lt="K109")
                )
                .order_by("folio", "c_sequence"),
            ),
        ]

        before_count = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()
        # master_source.siglum is None as of writing, matching the 19 existing
        # master-source chants — copying it through preserves that consistency.
        self.stdout.write(
            self.style.NOTICE(
                f"Master source {MASTER_SOURCE_ID} | siglum: {master_source.siglum!r}"
                f" | current chant count: {before_count}"
            )
        )

        total_to_copy = 0
        total_bad_folios = 0
        for label, qs in groups:
            count = qs.count()
            total_to_copy += count
            first = qs.first()
            last = qs.last()
            bad_folios = [
                c.folio
                for c in qs.iterator(chunk_size=500)
                if c.folio and not FOLIO_RE.match(c.folio)
            ]
            total_bad_folios += len(bad_folios)
            self.stdout.write(f"\n{label}")
            self.stdout.write(f"  Count: {count}")
            if first:
                self.stdout.write(
                    f"  First: folio={first.folio!r}, c_sequence={first.c_sequence}"
                )
            if last:
                self.stdout.write(
                    f"  Last:  folio={last.folio!r}, c_sequence={last.c_sequence}"
                )
            if bad_folios:
                self.stdout.write(
                    self.style.WARNING(
                        f"  WARNING: {len(bad_folios)} folio(s) fail regex: {bad_folios[:20]}"
                    )
                )
            else:
                self.stdout.write("  Folio format: OK")

        self.stdout.write(f"\nTotal to copy: {total_to_copy}")

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nDry run complete. No data written."))
            return

        if total_bad_folios:
            raise CommandError(
                f"Refusing to copy: {total_bad_folios} folio(s) do not match "
                f"{FOLIO_RE.pattern}. Re-run with --dry-run to inspect the offenders, "
                "then fix the source data or adjust the filter."
            )

        with transaction.atomic(), reversion.create_revision():
            reversion.set_comment("copy_chants_to_master_source: issue #2038")
            for label, qs in groups:
                group_count = 0
                for chant in qs.iterator(chunk_size=500):
                    proofread_by_pks = list(
                        chant.proofread_by.values_list("pk", flat=True)
                    )
                    chant.pk = None
                    chant.source = master_source
                    chant.siglum = master_source.siglum
                    chant.folio = chant.folio[1:] if chant.folio else chant.folio
                    # OneToOne to self with a uniqueness constraint; cleared so
                    # populate_next_chant_fields can rebuild the chain on the master.
                    chant.next_chant = None
                    chant.save()
                    if proofread_by_pks:
                        chant.proofread_by.set(proofread_by_pks)
                    group_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  {label}: done ({group_count} chants)")
                )

        after_count = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Master source chant count: {before_count} → {after_count}"
                f" (+{after_count - before_count})"
            )
        )
