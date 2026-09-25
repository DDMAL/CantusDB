from datetime import datetime, timezone as dt_timezone
from typing import Optional

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db.models import Model

from main_app.models import Chant, Sequence

BATCH_SIZE = 2000


def epoch_to_datetime(epoch: object) -> Optional[datetime]:
    try:
        return datetime.fromtimestamp(float(epoch), tz=dt_timezone.utc)  # type: ignore[arg-type]
    except (TypeError, ValueError, OSError):
        return None


class Command(BaseCommand):
    help = (
        "Backfill Chant/Sequence date_created, date_updated, and last_updated_by "
        "from the original OldCantus data stored in json_info (the 'created', "
        "'changed', and 'revision_uid' fields of the migrated Drupal node). "
        "date_created on migrated records currently just holds the 2023 "
        "migration timestamp; this replaces it with the real historical date. "
        "date_updated (auto_now) and last_updated_by are only backfilled for "
        "records where last_updated_by is still null -- that's the only "
        "reliable signal that no genuine edit has happened since migration, "
        "since bulk maintenance saves (e.g. touch_all_chants) also bump "
        "date_updated without setting last_updated_by. Once last_updated_by "
        "is set by a real edit, date_updated is never touched by this "
        "command again."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Compute and report what would change without writing anything.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        user_ids = set(get_user_model().objects.values_list("id", flat=True))
        for model in (Chant, Sequence):
            self.backfill_model(model, user_ids, dry_run)

    def backfill_model(
        self, model: type[Model], user_ids: set[int], dry_run: bool
    ) -> None:
        queryset = model.objects.exclude(json_info=None).iterator(chunk_size=BATCH_SIZE)
        batch = []
        updated = 0
        skipped_dates = 0
        skipped_changed = 0
        skipped_editor = 0
        skipped_malformed = 0

        for obj in queryset:
            info = obj.json_info
            if not isinstance(info, dict):
                skipped_malformed += 1
                continue

            changed = False
            # last_updated_by is only ever set by a genuine edit (the Create/Edit
            # views set it explicitly). Bulk maintenance saves (e.g.
            # touch_all_chants) bump date_updated via auto_now without setting
            # it, so its presence is the only reliable sign that date_updated
            # already reflects a real edit rather than migration/maintenance noise.
            already_edited = obj.last_updated_by_id is not None

            date_created = epoch_to_datetime(info.get("created"))
            if date_created is not None:
                obj.date_created = date_created
                changed = True
            else:
                skipped_dates += 1

            if not already_edited:
                date_updated = epoch_to_datetime(info.get("changed"))
                if date_updated is not None:
                    obj.date_updated = date_updated
                    changed = True
                else:
                    skipped_changed += 1

                try:
                    revision_uid = int(info["revision_uid"])
                except (KeyError, TypeError, ValueError):
                    revision_uid = None
                if revision_uid is not None and revision_uid in user_ids:
                    obj.last_updated_by_id = revision_uid
                    changed = True
                else:
                    skipped_editor += 1

            if changed:
                updated += 1
                if not dry_run:
                    batch.append(obj)

            if len(batch) >= BATCH_SIZE:
                model.objects.bulk_update(
                    batch, ["date_created", "date_updated", "last_updated_by"]
                )
                batch = []

        if batch:
            model.objects.bulk_update(
                batch, ["date_created", "date_updated", "last_updated_by"]
            )

        prefix = "[dry run] " if dry_run else ""
        self.stdout.write(
            self.style.SUCCESS(
                f"{prefix}{model.__name__}: {'would update' if dry_run else 'updated'} "
                f"{updated} records ({skipped_dates} missing a usable created date, "
                f"{skipped_changed} missing a usable changed date, "
                f"{skipped_editor} missing a resolvable revision editor, "
                f"{skipped_malformed} with malformed json_info)."
            )
        )
