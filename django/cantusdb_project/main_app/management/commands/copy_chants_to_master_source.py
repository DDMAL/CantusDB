import argparse
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
import reversion  # type: ignore[import-untyped]

from main_app.models import Chant, Source

MASTER_SOURCE_ID = 1000289
# Total rows the five folio ranges should yield. Drift here means the source sources have
# changed since #2038 was scoped; the operator should investigate before copying blindly.
EXPECTED_TOTAL = 709
FOLIO_RE = re.compile(r"^K\d{3}[A-Za-z]?$")


class Command(BaseCommand):
    help = f"Copy {EXPECTED_TOTAL} chants from student-work sources into the Kaiatonsera master source (issue #2038)."

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print per-group counts and sanity checks without writing any data.",
        )
        parser.add_argument(
            "--allow-drift",
            action="store_true",
            help=(
                "Proceed even if total_to_copy != EXPECTED_TOTAL. "
                "Only set this after verifying the dry-run output."
            ),
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        allow_drift: bool = options["allow_drift"]

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
        self.stdout.write(
            self.style.NOTICE(
                f"Master source {MASTER_SOURCE_ID} | siglum: {master_source.siglum!r}"
                f" | current chant count: {before_count}"
            )
        )

        total_to_copy = 0
        total_bad_folios = 0
        # Materialize each group's (id, folio, c_sequence) rows once so the
        # count / first / last / bad-folio scan / collision scan all reuse it.
        group_rows: list[tuple[str, list[tuple[int, str | None, int | None]]]] = []
        for label, qs in groups:
            rows = list(qs.values_list("id", "folio", "c_sequence"))
            group_rows.append((label, rows))
            count = len(rows)
            total_to_copy += count
            bad_folios = [
                (cid, folio) for cid, folio, _ in rows
                if folio and not FOLIO_RE.match(folio)
            ]
            total_bad_folios += len(bad_folios)
            self.stdout.write(f"\n{label}")
            self.stdout.write(f"  Count: {count}")
            if rows:
                _, first_folio, first_seq = rows[0]
                _, last_folio, last_seq = rows[-1]
                self.stdout.write(f"  First: folio={first_folio!r}, c_sequence={first_seq}")
                self.stdout.write(f"  Last:  folio={last_folio!r}, c_sequence={last_seq}")
            if bad_folios:
                preview = ", ".join(f"#{cid}={folio!r}" for cid, folio in bad_folios[:20])
                self.stdout.write(
                    self.style.WARNING(
                        f"  WARNING: {len(bad_folios)} folio(s) fail regex: {preview}"
                    )
                )
            else:
                self.stdout.write("  Folio format: OK")

        self.stdout.write(f"\nTotal to copy: {total_to_copy}")

        existing_master_slots: dict[tuple[str | None, int | None], int] = {
            (folio, c_seq): cid
            for cid, folio, c_seq in Chant.objects.filter(
                source_id=MASTER_SOURCE_ID
            ).values_list("id", "folio", "c_sequence")
        }
        collisions: list[tuple[int, int, str | None, int | None]] = []
        for _, rows in group_rows:
            for src_id, src_folio, c_seq in rows:
                new_folio = src_folio[1:] if src_folio else src_folio
                master_id = existing_master_slots.get((new_folio, c_seq))
                if master_id is not None:
                    collisions.append((master_id, src_id, new_folio, c_seq))

        if collisions:
            self.stdout.write(
                self.style.ERROR(
                    f"\nCOLLISION: {len(collisions)} (folio, c_sequence) slot(s) "
                    f"on master {MASTER_SOURCE_ID} are already occupied:"
                )
            )
            for master_id, src_id, folio, c_seq in collisions[:20]:
                self.stdout.write(
                    self.style.ERROR(
                        f"  master #{master_id} <-> src #{src_id} "
                        f"@ folio={folio!r}, c_sequence={c_seq}"
                    )
                )
            if len(collisions) > 20:
                self.stdout.write(
                    self.style.ERROR(f"  ... and {len(collisions) - 20} more")
                )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nDry run complete. No data written."))
            return

        if collisions:
            raise CommandError(
                f"Refusing to copy: {len(collisions)} (folio, c_sequence) slot(s) "
                f"already occupied on master {MASTER_SOURCE_ID}. Two chants cannot "
                "share the same page address. Re-run with --dry-run to see the full "
                "list, then resolve manually (delete the existing rows, narrow the "
                "source ranges, or coordinate with whoever added them)."
            )

        if total_to_copy != EXPECTED_TOTAL and not allow_drift:
            raise CommandError(
                f"Refusing to copy: total_to_copy={total_to_copy} but EXPECTED_TOTAL="
                f"{EXPECTED_TOTAL}. The source sources may have drifted since #2038 "
                "was scoped. Re-run with --dry-run to inspect; pass --allow-drift "
                "to proceed once you've confirmed the new count is correct."
            )

        if total_bad_folios:
            raise CommandError(
                f"Refusing to copy: {total_bad_folios} folio(s) do not match "
                f"{FOLIO_RE.pattern}. Re-run with --dry-run to inspect the offenders, "
                "then fix the source data or adjust the filter."
            )

        with transaction.atomic(), reversion.create_revision():
            reversion.set_comment("copy_chants_to_master_source: issue #2038")
            # Two passes so each copy's next_chant can point at the copy of its
            # original's successor. The OneToOneField forbids two rows sharing a
            # target, not "copying a pointer" — distinct PKs may target distinct
            # PKs without conflict.
            copies: dict[int, Chant] = {}
            original_next: dict[int, int | None] = {}

            for label, qs in groups:
                group_count = 0
                for chant in qs.prefetch_related("proofread_by"):
                    orig_id = chant.id
                    orig_next_id = chant.next_chant_id
                    proofread_by_pks = [u.pk for u in chant.proofread_by.all()]
                    chant.pk = None
                    chant.source = master_source
                    chant.folio = chant.folio[1:] if chant.folio else chant.folio
                    chant.next_chant = None
                    chant.save()
                    if proofread_by_pks:
                        chant.proofread_by.set(proofread_by_pks)
                    copies[orig_id] = chant
                    original_next[orig_id] = orig_next_id
                    group_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  {label}: done ({group_count} chants)")
                )

            # Rebind next_chant on each copy to the copy of its original's
            # successor; at group boundaries the successor is outside the
            # copy range and next_chant stays None. Use save(update_fields=...)
            # rather than QuerySet.update() so django-reversion captures the
            # rebound state — .update() bypasses signals and would leave the
            # revision frozen at pass-1's next_chant=None.
            # Why this matters: views/chant.py reads chant.next_chant directly
            # via select_related for feast-boundary detection. Chant.get_next_chant
            # itself recomputes from folio + c_sequence and ignores the FK.
            rebound = 0
            for orig_id, copy in copies.items():
                succ = original_next[orig_id]
                if succ is not None and succ in copies:
                    copy.next_chant = copies[succ]
                    copy.save(update_fields=["next_chant"])
                    rebound += 1
            self.stdout.write(
                self.style.SUCCESS(f"Rebound next_chant on {rebound} copies.")
            )

        after_count = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Master source chant count: {before_count} → {after_count}"
                f" (+{after_count - before_count})"
            )
        )
