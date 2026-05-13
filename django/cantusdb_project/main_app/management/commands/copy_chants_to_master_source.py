"""Copy chants from student-work sources into the Kaiatonsera master source.

One-shot command for issue #2038. `--dry-run` previews counts and sanity
checks; the real run is guarded against drift, malformed folios, and slot
collisions before any write.
"""

import argparse
import re
from collections.abc import Callable, Sequence
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q, QuerySet
import reversion  # type: ignore[import-untyped]

from main_app.models import Chant, Source

MASTER_SOURCE_ID = 1000289
# Total rows the five folio ranges should yield. Drift here may mean the source
# sources have changed since #2038 was scoped
EXPECTED_TOTAL = 709
FOLIO_RE = re.compile(r"^K\d{3}[A-Za-z]?$")

# (id, folio, c_sequence) tuples materialized from each group's queryset.
ScannedRow = tuple[int, str | None, int | None]
LabeledGroup = tuple[str, QuerySet[Chant]]
LabeledRows = tuple[str, list[ScannedRow]]
MasterCollision = tuple[int, int, str | None, int | None]
CrossCollision = tuple[str | None, int | None, list[int]]


class Command(BaseCommand):
    help = (
        f"Copy {EXPECTED_TOTAL} chants from student-work sources into the "
        "Kaiatonsera master source (issue #2038)."
    )

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

        master_source = self._get_master_source()
        groups = self._build_groups()
        self._print_master_summary(master_source)

        group_rows, total_to_copy, total_bad_folios = self._scan_groups(groups)
        self.stdout.write(f"\nTotal to copy: {total_to_copy}")

        collisions, cross_collisions = self._detect_collisions(group_rows)
        self._print_collisions(collisions, cross_collisions, dry_run=dry_run)

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("\nDry run complete. No data written.")
            )
            return

        self._enforce_guards(
            collisions=collisions,
            cross_collisions=cross_collisions,
            total_to_copy=total_to_copy,
            total_bad_folios=total_bad_folios,
            allow_drift=allow_drift,
        )

        before_count = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()
        with transaction.atomic(), reversion.create_revision():
            reversion.set_comment("copy_chants_to_master_source: issue #2038")
            self._copy_groups(groups, master_source)
        after_count = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Master source chant count: {before_count} → {after_count}"
            )
        )

    # -------------------- setup --------------------

    def _get_master_source(self) -> Source:
        try:
            return Source.objects.get(id=MASTER_SOURCE_ID)
        except Source.DoesNotExist as e:
            raise CommandError(f"Master source {MASTER_SOURCE_ID} not found.") from e

    def _build_groups(self) -> list[LabeledGroup]:
        # Five (source, folio range) groups specified by Debra in issue #2038.
        return [
            (
                "Group 1: source 1000260, K005–K028",
                Chant.objects.filter(
                    source_id=1000260,
                    folio__gte="K005",
                    folio__lt="K029",
                ).order_by("folio", "c_sequence"),
            ),
            (
                "Group 2: source 1000208, K039–K053",
                Chant.objects.filter(
                    source_id=1000208,
                    folio__gte="K039",
                    folio__lt="K054",
                ).order_by("folio", "c_sequence"),
            ),
            (
                "Group 3: source 1000260, K053(seq≥5)–K067",
                Chant.objects.filter(source_id=1000260)
                .filter(
                    Q(folio="K053", c_sequence__gte=5)
                    | Q(folio__gt="K053", folio__lt="K068")
                )
                .order_by("folio", "c_sequence"),
            ),
            (
                "Group 4: source 1000260, K082–K090",
                Chant.objects.filter(
                    source_id=1000260,
                    folio__gte="K082",
                    folio__lt="K091",
                ).order_by("folio", "c_sequence"),
            ),
            (
                "Group 5: source 1000208, K090(seq≥7)–K108",
                Chant.objects.filter(source_id=1000208)
                .filter(
                    Q(folio="K090", c_sequence__gte=7)
                    | Q(folio__gt="K090", folio__lt="K109")
                )
                .order_by("folio", "c_sequence"),
            ),
        ]

    def _print_master_summary(self, master_source: Source) -> None:
        before_count = Chant.objects.filter(source_id=MASTER_SOURCE_ID).count()
        self.stdout.write(
            self.style.NOTICE(
                f"Master source {MASTER_SOURCE_ID} | siglum: {master_source.siglum!r}"
                f" | current chant count: {before_count}"
            )
        )

    # -------------------- scan --------------------

    def _scan_groups(
        self, groups: list[LabeledGroup]
    ) -> tuple[list[LabeledRows], int, int]:
        # Materialize each group's (id, folio, c_sequence) rows once so the
        # count, sample rows, bad-folio scan, and collision scan all reuse it.
        group_rows: list[LabeledRows] = []
        total_to_copy = 0
        total_bad_folios = 0
        for label, qs in groups:
            rows: list[ScannedRow] = list(qs.values_list("id", "folio", "c_sequence"))
            bad_folios = [
                (cid, folio)
                for cid, folio, _ in rows
                if folio and not FOLIO_RE.match(folio)
            ]
            group_rows.append((label, rows))
            total_to_copy += len(rows)
            total_bad_folios += len(bad_folios)
            self._print_group_summary(label, rows, bad_folios)
        return group_rows, total_to_copy, total_bad_folios

    def _print_group_summary(
        self,
        label: str,
        rows: list[ScannedRow],
        bad_folios: list[tuple[int, str]],
    ) -> None:
        self.stdout.write(f"\n{label}")
        self.stdout.write(f"  Count: {len(rows)}")
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

    # -------------------- collisions --------------------

    def _detect_collisions(
        self, group_rows: list[LabeledRows]
    ) -> tuple[list[MasterCollision], list[CrossCollision]]:
        existing_master_slots: dict[tuple[str | None, int | None], int] = {
            (folio, c_seq): cid
            for cid, folio, c_seq in Chant.objects.filter(
                source_id=MASTER_SOURCE_ID
            ).values_list("id", "folio", "c_sequence")
        }
        # collisions: a copy would land on a slot already taken by an existing master row.
        # cross_collisions: two copies want the same slot.
        collisions: list[MasterCollision] = []
        copy_slots: dict[tuple[str | None, int | None], list[int]] = {}
        for _, rows in group_rows:
            for src_id, src_folio, c_seq in rows:
                new_folio = src_folio[1:] if src_folio else src_folio
                master_id = existing_master_slots.get((new_folio, c_seq))
                if master_id is not None:
                    collisions.append((master_id, src_id, new_folio, c_seq))
                copy_slots.setdefault((new_folio, c_seq), []).append(src_id)
        cross_collisions: list[CrossCollision] = [
            (folio, c_seq, ids)
            for (folio, c_seq), ids in copy_slots.items()
            if len(ids) > 1
        ]
        return collisions, cross_collisions

    def _print_collisions(
        self,
        collisions: list[MasterCollision],
        cross_collisions: list[CrossCollision],
        *,
        dry_run: bool,
    ) -> None:
        def _emit(
            header: str,
            rows: Sequence[Any],
            format_row: Callable[[Any], str],
        ) -> None:
            self.stdout.write(self.style.ERROR(header))
            preview = rows if dry_run else rows[:20]
            for row in preview:
                self.stdout.write(self.style.ERROR(format_row(row)))
            if not dry_run and len(rows) > 20:
                self.stdout.write(self.style.ERROR(f"  ... and {len(rows) - 20} more"))

        if collisions:
            _emit(
                f"\nCOLLISION: {len(collisions)} (folio, c_sequence) slot(s) "
                f"on master {MASTER_SOURCE_ID} are already occupied:",
                collisions,
                lambda r: (
                    f"  master #{r[0]} <-> src #{r[1]} "
                    f"@ folio={r[2]!r}, c_sequence={r[3]}"
                ),
            )
        if cross_collisions:
            _emit(
                f"\nCROSS-COPY COLLISION: {len(cross_collisions)} (folio, c_sequence) "
                "slot(s) would be occupied by multiple copies:",
                cross_collisions,
                lambda r: (
                    f"  src chants [{', '.join(f'#{cid}' for cid in r[2])}] "
                    f"-> folio={r[0]!r}, c_sequence={r[1]}"
                ),
            )

    # -------------------- guards --------------------

    def _enforce_guards(
        self,
        *,
        collisions: list[MasterCollision],
        cross_collisions: list[CrossCollision],
        total_to_copy: int,
        total_bad_folios: int,
        allow_drift: bool,
    ) -> None:
        if collisions:
            raise CommandError(
                f"Refusing to copy: {len(collisions)} (folio, c_sequence) slot(s) "
                f"already occupied on master {MASTER_SOURCE_ID}. Two chants cannot "
                "share the same page address. Re-run with --dry-run to see the full "
                "list, then resolve manually (delete the existing rows, narrow the "
                "source ranges, or coordinate with whoever added them)."
            )
        if cross_collisions:
            raise CommandError(
                f"Refusing to copy: {len(cross_collisions)} (folio, c_sequence) slot(s) "
                "would be occupied by multiple copies. The source folio ranges "
                "overlap, and two copies cannot share the same page address on master."
                "Re-run with --dry-run to see the full list, then narrow the source "
                "ranges or coordinate with the data owner before re-running."
            )
        if total_to_copy != EXPECTED_TOTAL and not allow_drift:
            raise CommandError(
                f"Refusing to copy: total_to_copy={total_to_copy} but EXPECTED_TOTAL="
                f"{EXPECTED_TOTAL}. The source sources may have drifted since #2038 "
                "was scoped. Re-run with --dry-run to inspect, then either pass "
                "--allow-drift for this one-time run, or bump EXPECTED_TOTAL in code "
                f"to {total_to_copy} if the new count is the new normal."
            )
        if total_bad_folios:
            raise CommandError(
                f"Refusing to copy: {total_bad_folios} folio(s) do not match "
                f"{FOLIO_RE.pattern}. Re-run with --dry-run to inspect the offenders, "
                "then fix the source data or adjust the filter."
            )

    # -------------------- copy --------------------

    def _copy_groups(self, groups: list[LabeledGroup], master_source: Source) -> None:
        # Pass 1: insert copies with next_chant=None, remembering each original's
        # successor id for pass 2. The OneToOneField on next_chant forbids two rows
        # sharing a target, not copying a pointer — distinct PKs may target distinct
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

        # Pass 2: rebind next_chant to the copy of each original's successor. At
        # group boundaries the successor is outside the copy range and next_chant
        # stays None. save(update_fields=...) is required so django-reversion
        # captures the rebind — QuerySet.update bypasses signals and would leave
        # the revision frozen at pass-1's next_chant=None.
        # views/chant.py reads chant.next_chant directly via select_related for
        # feast-boundary detection; Chant.get_next_chant itself recomputes from
        # folio + c_sequence and ignores the FK.
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
