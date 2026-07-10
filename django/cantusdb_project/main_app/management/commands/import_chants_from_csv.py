"""
Management command to import chants from a CSV file.

Usage:
    python manage.py import_chants_from_csv path/to/file.csv --dry-run
    python manage.py import_chants_from_csv path/to/file.csv

The CSV must contain a `source_id` column referencing an existing Source by
its numeric primary key. All other columns are mapped directly to Chant fields.
"""

import csv
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.contrib.auth import get_user_model
from main_app.models import Chant, Feast, Genre, Service, Source

User = get_user_model()


# Maps CSV column names (lowercase) to Chant model field names.
# Columns mapped to None are recognised but intentionally skipped.
COLUMN_MAP = {
    "source_id":             "source_id",
    "siglum":                "siglum",
    "marginalia":            "marginalia",
    "folio":                 "folio",
    "content structure":     "content_structure",
    "sequence":              "c_sequence",
    "incipit":               "incipit",
    "feast":                 "_feast_name",       # resolved to FK in validation
    "office":                "_service_abbr",     # resolved to FK in validation
    "genre":                 "_genre_name",       # resolved to FK in validation
    "position":              "position",
    "cantus_id":             "cantus_id",
    "mode":                  "mode",
    "finalis":               "finalis",
    "differentia":           "differentia",
    "fulltext_standardized": "manuscript_full_text_std_spelling",
    "fulltext_ms":           "manuscript_full_text",
    "fulltext_standardized_proofread": "_bool:manuscript_full_text_std_proofread",
    "fulltext_ms_proofread": "_bool:manuscript_full_text_proofread",
    "volpiano":              "volpiano",
    "volpiano_proofread":    "_bool:volpiano_proofread",
    "image_link":            "image_link",
    "melody_id":             "melody_id",
    "cao_concordances":      "cao_concordances",
    "addendum":              "addendum",
    "extra":                 "extra",
    "indexing_notes":        "indexing_notes",
    "node_id":               "_node_id",  # old cantusdatabase.org ID → json_info["nid"]
    "frag_id":               None,        # fragmentarium ID — skip as it is a source-level attribute
}


class Command(BaseCommand):
    help = "Import chants from a CSV file into the database."

    def _build_chant_data(self, row, source_cache, feast_cache, service_cache, genre_cache):
        # visible_status '1' = published; legacy field from old Cantus, not used in current views
        chant_data = {"visible_status": "1"}
        for field, value in row.items():
            if field == "source_id":
                chant_data["source"] = source_cache[value]
            elif field == "_feast_name":
                chant_data["feast"] = feast_cache.get(value) if value else None
            elif field == "_service_abbr":
                chant_data["service"] = service_cache.get(value) if value else None
            elif field == "_genre_name":
                chant_data["genre"] = genre_cache.get(value) if value else None
            elif field == "_node_id":
                if value:
                    chant_data["json_info"] = {"nid": value}
            else:
                chant_data[field] = value
        return chant_data

    def add_arguments(self, parser):
        parser.add_argument("csv_file", type=str, help="Path to the CSV file")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate the CSV without writing to the database",
        )

    def handle(self, *args, **options):
        csv_path = options["csv_file"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write("(Dry-run mode: no database changes will be made.)")

        # ── Read CSV and map columns to Chant field names ──────

        if not os.path.exists(csv_path):
            raise CommandError(f"CSV file not found: {csv_path}")

        self.stdout.write(f"Reading {csv_path}...")

        try:
            with open(csv_path, newline="", encoding="utf-8-sig") as fh:
                reader = csv.DictReader(fh)
                raw_columns = reader.fieldnames
                if not raw_columns:
                    raise CommandError("CSV is empty (no header)")
                raw_rows = list(reader)
        except csv.Error as exc:
            raise CommandError(f"Error reading CSV: {exc}")

        if not raw_rows:
            raise CommandError("CSV is empty (no rows)")

        if "source_id" not in {col.lower() for col in raw_columns}:
            raise CommandError("CSV is missing source_id")

        # Report mapped / skipped / unknown columns
        mapped_cols, skipped_cols, unknown_cols = [], [], []
        for col in raw_columns:
            key = col.lower()
            if key not in COLUMN_MAP:
                unknown_cols.append(col)
            elif COLUMN_MAP[key] is None:
                skipped_cols.append(col)
            else:
                mapped_cols.append(col)

        self.stdout.write(f"Found {len(raw_rows)} data row(s) and {len(raw_columns)} column(s).")
        self.stdout.write(f"  Mapped  : {', '.join(mapped_cols)}")

        if skipped_cols:
            self.stdout.write(f"  Skipped : {', '.join(skipped_cols)}")
        if unknown_cols:
            self.stdout.write(f"  Unknown : {', '.join(unknown_cols)}")

        # Build mapped_rows
        mapped_rows = []
        errors = []
        for row_num, raw_row in enumerate(raw_rows, start=2):
            mapped_row = {}
            for col, raw_value in raw_row.items():
                field = COLUMN_MAP.get(col.lower())
                if field is None:
                    continue  # skipped or unknown column

                value = raw_value.strip() if raw_value else ""

                if value == "":
                    real_key = field[6:] if field.startswith("_bool:") else field
                    mapped_row[real_key] = None
                    continue

                if field == "source_id":
                    try:
                        mapped_row[field] = int(value)
                    except ValueError:
                        errors.append(
                            f"Row {row_num}: source_id '{value}' is not a valid integer"
                        )
                elif field == "c_sequence":
                    try:
                        mapped_row[field] = int(value)
                    except ValueError:
                        errors.append(
                            f"Row {row_num}: sequence '{value}' is not a valid integer"
                        )
                elif field.startswith("_bool:"):
                    real_field = field[6:]
                    if value == "1":
                        mapped_row[real_field] = True
                    elif value == "0":
                        mapped_row[real_field] = False
                    else:
                        self.stdout.write(
                            self.style.WARNING(
                                f"Row {row_num}: {real_field} '{value}' is not 0 or 1 — storing NULL"
                            )
                        )
                        mapped_row[real_field] = None
                else:
                    mapped_row[field] = value

            mapped_rows.append(mapped_row)

        # ── Validate ───────

        self.stdout.write("Validating data...")

        # Caches so each unique value is only looked up once.
        source_cache  = {}  # int    Source object | "NOT_FOUND"
        feast_cache   = {}  # str    Feast object  | "NOT_FOUND"
        service_cache = {}  # str    Service object | "NOT_FOUND"
        genre_cache   = {}  # str    Genre object  | "NOT_FOUND"

        for i, row in enumerate(mapped_rows, start=2):

            # source_id is required
            sid = row.get("source_id")
            if sid is None:
                errors.append(f"Row {i}: source_id is required but missing or empty")
            else:
                if sid not in source_cache:
                    try:
                        source_cache[sid] = Source.objects.get(pk=sid)
                    except Source.DoesNotExist:
                        source_cache[sid] = "NOT_FOUND"
                if source_cache[sid] == "NOT_FOUND":
                    errors.append(f"Row {i}: Source with ID {sid} not found")

            # feast is optional
            feast_name = row.get("_feast_name")
            if feast_name:
                if feast_name not in feast_cache:
                    obj = Feast.objects.filter(name__iexact=feast_name).first()
                    feast_cache[feast_name] = obj if obj else "NOT_FOUND"
                if feast_cache[feast_name] == "NOT_FOUND":
                    errors.append(f"Row {i}: Feast '{feast_name}' not found")

            # service and office is optional
            service_abbr = row.get("_service_abbr")
            if service_abbr:
                if service_abbr not in service_cache:
                    obj = Service.objects.filter(name__iexact=service_abbr).first()
                    service_cache[service_abbr] = obj if obj else "NOT_FOUND"
                if service_cache[service_abbr] == "NOT_FOUND":
                    errors.append(f"Row {i}: Service '{service_abbr}' not found")

            # warning if shorter than 6 chars (may be missing leading zeros)
            cantus_id = row.get("cantus_id")
            if cantus_id and len(cantus_id) < 6:
                self.stdout.write(
                    self.style.WARNING(
                        f"Row {i}: cantus_id '{cantus_id}' is {len(cantus_id)} char(s)"
                    )
                )

            # genre is optional
            genre_name = row.get("_genre_name")
            if genre_name:
                if genre_name not in genre_cache:
                    obj = Genre.objects.filter(name__iexact=genre_name).first()
                    genre_cache[genre_name] = obj if obj else "NOT_FOUND"
                if genre_cache[genre_name] == "NOT_FOUND":
                    errors.append(f"Row {i}: Genre '{genre_name}' not found")

        if errors:
            self.stdout.write(self.style.ERROR(f"Validation failed with {len(errors)} error(s):"))
            for err in errors:
                self.stdout.write(f"  {err}")
            raise CommandError("Fix the errors in the CSV and try again.")

        self.stdout.write(
            self.style.SUCCESS(f"All {len(mapped_rows)} row(s) validated successfully.")
        )

        # ── Model-level validation (dry-run only) ──────────────────────────────────
        # Calls full_clean() on each unsaved Chant so field-level constraints
        # (URLField format, max_length, choice validation) are caught before import.

        if dry_run:
            model_errors = []
            for i, row in enumerate(mapped_rows, start=2):
                chant_data = self._build_chant_data(row, source_cache, feast_cache, service_cache, genre_cache)
                try:
                    Chant(**chant_data).full_clean()
                except Exception as exc:
                    model_errors.append(f"Row {i}: {exc}")
            if model_errors:
                self.stdout.write(self.style.ERROR(f"Model validation failed with {len(model_errors)} error(s):"))
                for err in model_errors:
                    self.stdout.write(f"  {err}")
                raise CommandError("Fix the errors in the CSV and try again.")

        # ── Duplicate detection (apply during the dry-run only) ─────────────────────
        # We check for duplicates within the CSV and against existing database records based on
        # the unique key (source_id, folio, c_sequence). This is only happens in dry-run mode
        # as a warning to the user, since in some cases they may intentionally want to import duplicates
        # This is omitted during actual import to avoid false positives
        
        if dry_run:
            self.stdout.write("Checking for duplicates...")
            warnings = []
            seen_keys = {}  # (source_id, folio, c_sequence) → first row number

            # Fetch all potentially matching chants in one query keyed by (source_id, folio, c_sequence)
            source_ids = {row.get("source_id") for row in mapped_rows if row.get("source_id")}
            db_existing: dict[tuple, list[int]] = {}
            for chant_id, sid, folio, seq in (
                Chant.objects.filter(source_id__in=source_ids)
                .values_list("id", "source_id", "folio", "c_sequence")
            ):
                db_existing.setdefault((sid, folio, seq), []).append(chant_id)

            for i, row in enumerate(mapped_rows, start=2):
                key = (row.get("source_id"), row.get("folio"), row.get("c_sequence"))

                # CSV-internal duplicates
                if key in seen_keys:
                    warnings.append(
                        f"Row {i} & Row {seen_keys[key]}: duplicate within CSV"
                        f" (source {key[0]}, folio {key[1]}, seq {key[2]})"
                    )
                else:
                    seen_keys[key] = i

                # Database duplicates (in-memory lookup)
                existing = db_existing.get(key, [])
                if existing:
                    warnings.append(
                        f"Row {i}: already exists in database"
                        f" (source {key[0]}, folio {key[1]}, seq {key[2]})"
                        f" — chant ID(s): {', '.join(str(x) for x in existing)}"
                    )

            if warnings:
                self.stdout.write(self.style.WARNING(f"Found {len(warnings)} duplicate warning(s):"))
                for w in warnings:
                    self.stdout.write(f"  {w}")
            else:
                self.stdout.write(self.style.SUCCESS("No duplicates found."))

            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete — {len(mapped_rows)} row(s) validated, ready to import."
                )
            )
            return

        # ── Prepare chant data and create records ─────────────

        self.stdout.write("Creating chants...")

        # Get admin user (id==1 in both staging and production) to set as created_by for all imported chants.
        admin_user = User.objects.get(id=1)
        created_count = 0

        with transaction.atomic():
            for row in mapped_rows:
                chant_data = self._build_chant_data(row, source_cache, feast_cache, service_cache, genre_cache)
                chant_data["created_by"] = admin_user
                Chant(**chant_data).save()
                created_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Successfully imported {created_count} chant(s).")
        )