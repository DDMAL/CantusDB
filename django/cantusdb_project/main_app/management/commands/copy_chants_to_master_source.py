import argparse
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
import reversion  # type: ignore[import-untyped]

from main_app.models import Chant, Source

MASTER_SOURCE_ID = 1000289
# Pre-copy chant count on the master source. Used as an idempotency guard:
# a non-matching count means the command likely already ran and re-running would create duplicates.
EXPECTED_MASTER_BASELINE = 19
# Total rows the five folio ranges should yield. Drift here means the source sources have
# changed since #2038 was scoped; the operator should investigate before copying blindly.
EXPECTED_TOTAL = 705
FOLIO_RE = re.compile(r"^K\d{3}[A-Za-z]?$")
# Used to detect semantic folio collisions where master and the source disagree
# on zero-padding (e.g. '89' vs '089' are the same physical page).
LEADING_ZEROS_RE = re.compile(r"(?<!\d)0+(?=\d)")


def _normalize_folio(folio: str | None) -> str | None:
    """Strip leading zeros from each numeric segment so '089' and '89' compare equal."""
    if not folio:
        return folio
    return LEADING_ZEROS_RE.sub("", folio)


class Command(BaseCommand):
    help = "Copy 705 chants from student-work sources into the Kaiatonsera master source (issue #2038)."

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
        for label, qs in groups:
            count = qs.count()
            total_to_copy += count
            first = qs.first()
            last = qs.last()
            bad_folios = [
                (c.id, c.folio)
                for c in qs.only("id", "folio").iterator(chunk_size=500)
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
                preview = ", ".join(f"#{cid}={folio!r}" for cid, folio in bad_folios[:20])
                self.stdout.write(
                    self.style.WARNING(
                        f"  WARNING: {len(bad_folios)} folio(s) fail regex: {preview}"
                    )
                )
            else:
                self.stdout.write("  Folio format: OK")

        self.stdout.write(f"\nTotal to copy: {total_to_copy}")

        # Key on the normalized folio so '89' and '089' (same physical page,
        # different zero-padding conventions) compare as equal.
        existing_master_slots: dict[tuple[str | None, int | None], tuple[int, str | None]] = {
            (_normalize_folio(folio), c_seq): (cid, folio)
            for cid, folio, c_seq in Chant.objects.filter(
                source_id=MASTER_SOURCE_ID
            ).values_list("id", "folio", "c_sequence")
        }
        collisions: list[tuple[int, str | None, int, str | None, int | None]] = []
        for _, qs in groups:
            for src_id, src_folio, c_seq in qs.values_list("id", "folio", "c_sequence"):
                new_folio = src_folio[1:] if src_folio else src_folio
                match = existing_master_slots.get((_normalize_folio(new_folio), c_seq))
                if match is not None:
                    master_cid, master_folio = match
                    collisions.append((master_cid, master_folio, src_id, new_folio, c_seq))

        if collisions:
            self.stdout.write(
                self.style.ERROR(
                    f"\nCOLLISION: {len(collisions)} (folio, c_sequence) slot(s) "
                    f"on master {MASTER_SOURCE_ID} are already occupied:"
                )
            )
            for master_id, master_folio, src_id, src_folio_stripped, c_seq in collisions[:20]:
                marker = "" if master_folio == src_folio_stripped else "  [folio normalized]"
                self.stdout.write(
                    self.style.ERROR(
                        f"  master #{master_id} (folio={master_folio!r}) "
                        f"<-> src #{src_id} (folio={src_folio_stripped!r}) "
                        f"@ c_sequence={c_seq}{marker}"
                    )
                )
            if len(collisions) > 20:
                self.stdout.write(
                    self.style.ERROR(f"  ... and {len(collisions) - 20} more")
                )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("\nDry run complete. No data written."))
            return

        if before_count != EXPECTED_MASTER_BASELINE:
            raise CommandError(
                f"Master source has {before_count} chants but the expected pre-copy "
                f"baseline is {EXPECTED_MASTER_BASELINE}. This command is one-shot; "
                "re-running it would create duplicates. If the current state is "
                f"intentional, update EXPECTED_MASTER_BASELINE in {__name__}."
            )

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
            for label, qs in groups:
                group_count = 0
                for chant in qs.prefetch_related("proofread_by"):
                    proofread_by_pks = [u.pk for u in chant.proofread_by.all()]
                    chant.pk = None
                    chant.source = master_source
                    chant.folio = chant.folio[1:] if chant.folio else chant.folio
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
