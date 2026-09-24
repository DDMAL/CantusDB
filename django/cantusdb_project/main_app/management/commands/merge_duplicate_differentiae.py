"""Merge duplicate Differentia rows caused by untrimmed differentia_id values
(issue #1776). A stray trailing space (e.g. "101b ") creates a new row instead
of matching the existing "101b", so chants pointing at the whitespace variant
never show up as the same differentia.

For each group of differentia_id values that are identical once whitespace is
stripped, the row with the exact stripped id is kept as canonical; every other
row in the group has its chants (Chant.diff_db) repointed to the canonical row
and is then deleted. Information the duplicates carry (mode, melodic
transcription) is backfilled onto the canonical row first, so that merging
never drops data -- see _plan_field_updates.

T31A is a manually-confirmed typo (see #1776), not a whitespace issue: Anna
checked DifferentiaeDB and confirmed there is no case-variant "T31A" code, so
it's folded into "T31a" via CASE_TYPO_ALIASES rather than by generic
normalization, since differentia_id is otherwise case-sensitive.

The merge is destructive, so each group's pre-merge state is written to its own
revision before anything changes -- see _snapshot_pre_merge.
"""

import argparse
from collections import defaultdict
from typing import Any

import reversion  # type: ignore[import-untyped]
from django.core.management.base import BaseCommand
from django.db import transaction

from main_app.models import Differentia

CASE_TYPO_ALIASES = {"T31A": "T31a"}

# Fields holding differentia information beyond the identifier itself. #1776
# asks for the row "with more information (mode and volpiano)" to survive the
# merge; these are the fields that carry it.
INFORMATION_FIELDS = ("mode", "melodic_transcription")


def normalize(differentia_id: str) -> str:
    stripped = differentia_id.strip()
    return CASE_TYPO_ALIASES.get(stripped, stripped)


class Command(BaseCommand):
    help = (
        "Merge duplicate Differentia rows that only differ by whitespace "
        "(issue #1776). Repoints affected chants to the canonical row, then "
        "deletes the duplicate. Use --dry-run to preview without writing."
    )

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print the merge plan without writing any data.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]

        groups = self._build_groups()
        if not groups:
            self.stdout.write(self.style.SUCCESS("No duplicate differentiae found."))
            return

        for key, members in groups.items():
            canonical = self._pick_canonical(key, members)
            duplicates = [d for d in members if d.pk != canonical.pk]
            updates, conflicts = self._plan_field_updates(canonical, duplicates)
            self._print_group(canonical, duplicates, updates, conflicts)

            if not dry_run:
                with transaction.atomic():
                    self._snapshot_pre_merge(canonical, duplicates)
                    with reversion.create_revision():
                        reversion.set_comment(
                            "merge_duplicate_differentiae: issue #1776"
                        )
                        self._merge_group(canonical, duplicates, updates)

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("\nDry run complete. No data written.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"\nMerged {len(groups)} duplicate group(s).")
            )

    def _build_groups(self) -> dict[str, list[Differentia]]:
        by_key: dict[str, list[Differentia]] = defaultdict(list)
        for differentia in Differentia.objects.all():
            by_key[normalize(differentia.differentia_id)].append(differentia)
        return {key: members for key, members in by_key.items() if len(members) > 1}

    def _pick_canonical(self, key: str, members: list[Differentia]) -> Differentia:
        exact_matches = [d for d in members if d.differentia_id == key]
        if exact_matches:
            return min(exact_matches, key=lambda d: d.pk)
        # No member's raw id matches the normalized key exactly (shouldn't
        # happen for whitespace-only groups). Fall back to the row with the
        # lowest pk, i.e. the one most likely to already be in use elsewhere.
        return min(members, key=lambda d: d.pk)

    def _plan_field_updates(
        self, canonical: Differentia, duplicates: list[Differentia]
    ) -> tuple[dict[str, str], list[str]]:
        """Work out which information fields to copy from the duplicates onto
        the canonical row, and flag any disagreement for a human to settle.

        The canonical row is picked for its clean differentia_id, which is not
        necessarily the row carrying the most information -- promoting the
        better-populated row instead would leave a trailing space in the id and
        defeat the point of the merge. So empty fields are backfilled from the
        duplicates rather than deleted along with them. A duplicate that
        disagrees with a value the canonical already holds never overwrites it;
        it is reported and left alone.
        """
        updates: dict[str, str] = {}
        conflicts: list[str] = []
        for field in INFORMATION_FIELDS:
            canonical_value = (getattr(canonical, field) or "").strip()
            for dup in sorted(duplicates, key=lambda d: d.pk):
                value = (getattr(dup, field) or "").strip()
                if not value:
                    continue
                kept = updates.get(field, canonical_value)
                if not kept:
                    updates[field] = value
                elif value != kept:
                    conflicts.append(
                        f"{field}: keeping {kept!r}, ignoring {value!r} "
                        f"from id={dup.pk}"
                    )
        return updates, conflicts

    def _print_group(
        self,
        canonical: Differentia,
        duplicates: list[Differentia],
        updates: dict[str, str],
        conflicts: list[str],
    ) -> None:
        self.stdout.write(
            f"\nCanonical: {canonical.differentia_id!r} (id={canonical.pk})"
        )
        for dup in duplicates:
            chant_count = dup.chant_set.count()
            self.stdout.write(
                f"  Duplicate: {dup.differentia_id!r} (id={dup.pk}), "
                f"{chant_count} chant(s) to repoint"
            )
        for field, value in updates.items():
            self.stdout.write(f"  Backfill: {field} = {value!r}")
        for conflict in conflicts:
            self.stdout.write(self.style.WARNING(f"  Conflict: {conflict}"))

    def _snapshot_pre_merge(
        self, canonical: Differentia, duplicates: list[Differentia]
    ) -> None:
        """Record the pre-merge state in a revision of its own.

        This has to be a separate revision that closes before the merge runs.
        django-reversion discards versions of rows that no longer exist when a
        revision closes, so a snapshot taken in the same revision as the delete
        is thrown away; and its post_save handler overwrites any earlier
        snapshot of an object with that object's post-save state, so the old
        Chant.diff_db link would be overwritten by the new one. Snapshotting
        here leaves the deleted rows and the original links recoverable.
        """
        with reversion.create_revision():
            reversion.set_comment(
                "merge_duplicate_differentiae: pre-merge snapshot (issue #1776)"
            )
            reversion.add_to_revision(canonical)
            for dup in duplicates:
                reversion.add_to_revision(dup)
                for chant in dup.chant_set.all():
                    reversion.add_to_revision(chant)

    def _merge_group(
        self,
        canonical: Differentia,
        duplicates: list[Differentia],
        updates: dict[str, str],
    ) -> None:
        if updates:
            for field, value in updates.items():
                setattr(canonical, field, value)
            canonical.save(update_fields=list(updates))
        for dup in duplicates:
            for chant in dup.chant_set.all():
                chant.diff_db = canonical
                chant.save(update_fields=["diff_db"])
            dup.delete()
