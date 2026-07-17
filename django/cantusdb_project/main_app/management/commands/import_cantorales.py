"""
One-off management command to import sources from the
"cantorales_2024-05-01.csv" spreadsheet into CantusDB.

Sources are tagged with the Cantorales segment (settings.CANTORALES_SEGMENT_ID)
so they appear on /Cantorales/ but NOT on /sources/?segment=4063 (CANTUS Database).
"""

import csv
import os
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from main_app.models import (
    Century,
    Institution,
    Segment,
    Source,
)
from main_app.models.source_url import SourceURL

User = get_user_model()


CSV_FILENAME = "cantorales_2024-05-01.csv"

# CSV column indices
COL_RISM = 1
COL_SHELFMARK = 2
COL_CITY = 3
COL_ARCHIVE = 4
COL_CONDITION = 5
COL_LEAVES = 6
COL_MATERIAL = 7
COL_SOURCE_TYPE = 8
COL_CHANT_TYPE = 9
COL_CENTURY = 10
COL_DATE = 11
COL_STAVES = 12
COL_STAFF_LINES = 13
COL_COLOPHON = 14
COL_ORIGINS = 15
COL_OWNERS = 16
COL_TEXT_SCRIPT = 17
COL_NOTATION = 18
COL_BINDING = 19
COL_NOTES = 20
COL_IMAGES = 21
COL_ARCHIVE_LINK = 22
# COL_CANTUSDB_LINK = 23  — self-referential, not imported
COL_CONTRIBUTOR = 24
COL_CONTRIBUTOR_EMAIL = 25
COL_DATE_ENTERED = 26
COL_SOURCE_OF_DATA = 27

# Condition → Source.source_completeness
CONDITION_MAP = {
    "1": Source.SourceCompletenessChoices.FULL_SOURCE,  # complete
    "2": Source.SourceCompletenessChoices.FRAGMENTED,  # partial
    "3": Source.SourceCompletenessChoices.FRAGMENT,  # fragment
    "4": Source.SourceCompletenessChoices.FRAGMENT,  # binding waste
    "5": Source.SourceCompletenessChoices.UNKNOWN,  # unknown
}

MATERIAL_MAP = {
    "1": "Parchment",
    "2": "Paper",
    "3": "Parchment and paper",
    "4": "Unknown material",
}

SOURCE_TYPE_MAP = {
    "1": "Antiphonal",
    "2": "Gradual",
    "3": "Hymnal",
    "4": "Processional",
    "5": "Unknown",
}

CHANT_TYPE_MAP = {
    "1": "Hispanic",
    "2": "Franco-Roman",
    "3": "Unknown",
}


def ordinal(n):
    """Return e.g. '16th' for 16."""
    if 11 <= n % 100 <= 13:
        return f"{n:02d}th"
    return f"{n:02d}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def parse_centuries(raw):
    """
    Parse century strings like '16', '16, 17', '15-17' into a list of
    Century names like ['16th century', '17th century'].

    Handles comma-separated values ("16, 17"), dash ranges ("15-17"
    expands to 15th, 16th, 17th), and slash separators.
    """
    if not raw:
        return []
    names = []
    # Split on commas first (to handle "16, 17" or "15-16, 18")
    for part in re.split(r"[,/]+", raw):
        part = part.strip()
        if not part:
            continue
        # Check for a dash range like "15-17"
        range_match = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if range_match:
            start = int(range_match.group(1))
            end = int(range_match.group(2))
            for n in range(start, end + 1):
                names.append(f"{ordinal(n)} century")
        elif part.isdigit():
            names.append(f"{ordinal(int(part))} century")
    return names


def build_description(row):
    """Compile the free-text metadata columns into a description block."""
    parts = []

    material = MATERIAL_MAP.get(row[COL_MATERIAL].strip(), "")
    if material:
        parts.append(f"Material: {material}")

    source_types = [
        SOURCE_TYPE_MAP.get(t.strip(), "")
        for t in row[COL_SOURCE_TYPE].split(",")
        if t.strip()
    ]
    source_types = [s for s in source_types if s]
    if source_types:
        parts.append(f"Source type: {', '.join(source_types)}")

    chant_type = CHANT_TYPE_MAP.get(row[COL_CHANT_TYPE].strip(), "")
    if chant_type:
        parts.append(f"Chant type: {chant_type}")

    leaves = row[COL_LEAVES].strip()
    if leaves:
        parts.append(f"Leaves/pages: {leaves}")

    staves = row[COL_STAVES].strip()
    if staves:
        parts.append(f"Staves per side: {staves}")

    staff_lines = row[COL_STAFF_LINES].strip()
    if staff_lines:
        parts.append(f"Staff lines: {staff_lines}")

    colophon_map = {"1": "Yes", "2": "No", "3": "Unknown"}
    colophon = colophon_map.get(row[COL_COLOPHON].strip(), "")
    if colophon:
        parts.append(f"Colophon: {colophon}")

    for label, col in [
        ("Owners/dedicatees", COL_OWNERS),
        ("Text script", COL_TEXT_SCRIPT),
        ("Notation", COL_NOTATION),
        ("Binding", COL_BINDING),
        ("Notes", COL_NOTES),
    ]:
        val = row[col].strip()
        if val:
            parts.append(f"{label}: {val}")

    return "\n".join(parts) if parts else ""


class Command(BaseCommand):
    help = "Import sources from the USA-1 Cantorales CSV into CantusDB."

    @transaction.atomic
    def handle(self, *args, **options):
        csv_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "..",
            CSV_FILENAME,
        )
        csv_path = os.path.normpath(csv_path)

        if not os.path.exists(csv_path):
            self.stderr.write(f"CSV not found at {csv_path}")
            return

        cantorales_segment = Segment.objects.get(pk=settings.CANTORALES_SEGMENT_ID)

        # Pre-fetch century lookup
        century_by_name = {c.name: c for c in Century.objects.all()}

        # Create stub User accounts for contributors (unusable passwords)
        contributor_users = self._ensure_contributor_users(csv_path)

        created_count = 0
        skipped_existing_count = 0
        skipped_count = 0
        institution_created_count = 0

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader)  # header row
            next(reader)  # REQUIRED row
            next(reader)  # SAMPLE row

            for row_num, row in enumerate(reader, start=4):
                # Pad short rows
                while len(row) < 33:
                    row.append("")

                rism = row[COL_RISM].strip().strip("\n")
                shelfmark = row[COL_SHELFMARK].strip().strip("\n")

                # Skip empty rows
                if not rism and not shelfmark:
                    continue

                if not shelfmark:
                    self.stdout.write(
                        f"  Row {row_num}: skipping — no shelfmark (RISM={rism!r})"
                    )
                    skipped_count += 1
                    continue

                if not rism:
                    self.stdout.write(
                        f"  Row {row_num}: warning — no RISM siglum (shelfmark={shelfmark!r}), "
                        f"source will have no holding institution"
                    )

                # --- Institution ---
                institution = None
                if rism:
                    try:
                        institution = Institution.objects.get(siglum=rism)
                    except Institution.DoesNotExist:
                        city = row[COL_CITY].strip()
                        archive_name = row[COL_ARCHIVE].strip() or "[No Name]"
                        # Derive country from RISM prefix (US-xxx → US)
                        country_code = rism.split("-")[0] if "-" in rism else ""
                        country = {
                            "US": "United States",
                        }.get(country_code, country_code)
                        institution = Institution.objects.create(
                            siglum=rism,
                            name=archive_name,
                            city=city or None,
                            country=country or "[No Country]",
                        )
                        institution_created_count += 1
                        self.stdout.write(
                            f"  Created institution: {institution} ({rism})"
                        )

                # --- Skip existing sources entirely (issue #2059) ---
                # An earlier version of this import used update_or_create, which
                # overwrote curated metadata and added unexpected editors on
                # sources that already existed in CDB. We now refuse to modify
                # any existing source: if one already matches
                # (holding_institution, shelfmark) we skip the whole row
                if Source.objects.filter(
                    holding_institution=institution, shelfmark=shelfmark
                ).exists():
                    skipped_existing_count += 1
                    self.stdout.write(
                        f"  Row {row_num}: SKIP — source already exists, leaving "
                        f"it untouched: {institution} {shelfmark}"
                    )
                    continue

                # --- Source completeness ---
                condition_raw = row[COL_CONDITION].strip()
                completeness = CONDITION_MAP.get(
                    condition_raw, Source.SourceCompletenessChoices.UNKNOWN
                )

                # --- Provenance notes (from Origins and History) ---
                # The Origins column is free text (e.g. "Seville? Spain"), so
                # it stays in provenance_notes; we don't derive a controlled
                # Provenance taxonomy entry from it.
                provenance_notes = row[COL_ORIGINS].strip() or None

                # --- Description ---
                description = build_description(row)

                # --- Date ---
                date = row[COL_DATE].strip() or None

                # --- Image link ---
                image_link = row[COL_IMAGES].strip() or None

                # --- Indexing date (from "Date data entered") ---
                indexing_date = row[COL_DATE_ENTERED].strip() or None

                # --- Indexing notes (from "Source of data entered") ---
                source_of_data = row[COL_SOURCE_OF_DATA].strip()
                indexing_notes = (
                    f"Source of data: {source_of_data}" if source_of_data else None
                )

                # --- Create the new Source ---
                source = Source.objects.create(
                    holding_institution=institution,
                    shelfmark=shelfmark,
                    source_completeness=completeness,
                    provenance_notes=provenance_notes,
                    date=date,
                    description=description or None,
                    image_link=image_link,
                    indexing_date=indexing_date,
                    indexing_notes=indexing_notes,
                    source_status="Unpublished / No indexing activity",
                    published=True,
                )
                created_count += 1

                # --- Segment (Cantorales) ---
                source.segment_m2m.add(cantorales_segment)

                # --- Centuries ---
                century_names = parse_centuries(row[COL_CENTURY].strip())
                for cname in century_names:
                    century_obj = century_by_name.get(cname)
                    if century_obj:
                        source.century.add(century_obj)
                    else:
                        self.stdout.write(
                            f"  Row {row_num}: century not found: {cname!r}"
                        )

                # --- Archive permalink → SourceURL ---
                archive_link = row[COL_ARCHIVE_LINK].strip()
                if archive_link:
                    SourceURL.objects.get_or_create(
                        source=source,
                        url=archive_link,
                        defaults={
                            "url_type": SourceURL.URLTypes.HOST_INSTITUTION_RECORD,
                        },
                    )

                # --- Link contributor users ---
                contributor_raw = row[COL_CONTRIBUTOR].strip()
                if contributor_raw:
                    for name in re.split(r",\s*", contributor_raw):
                        name = name.strip()
                        if name in contributor_users:
                            source.source_data_contributed_by.add(
                                contributor_users[name]
                            )

                self.stdout.write(f"  Created source: {source} (row {row_num})")

        self.stdout.write("")
        self.stdout.write(
            f"Done. Created {created_count}, "
            f"skipped {skipped_existing_count} already-existing, "
            f"skipped {skipped_count} invalid. "
            f"New institutions: {institution_created_count}."
        )

    def _ensure_contributor_users(self, csv_path):
        """
        Create User accounts (unusable passwords) for each individual
        contributor in the CSV.  Returns {full_name: User}.

        The CSV often lists multiple people in one contributor field
        ("Victor Williams, Milton Gomez") with a single shared email.
        When a person appears as the sole contributor on at least one
        row we use that email; otherwise a .invalid placeholder is used.
        """
        # First pass: collect {name: set(emails)} and sole-row emails
        name_emails = {}
        sole_email = {}
        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            next(reader)
            next(reader)
            next(reader)  # header, REQUIRED, SAMPLE
            for row in reader:
                while len(row) < 33:
                    row.append("")
                raw_names = row[COL_CONTRIBUTOR].strip()
                email = row[COL_CONTRIBUTOR_EMAIL].strip()
                if not raw_names:
                    continue
                names = [n.strip() for n in re.split(r",\s*", raw_names) if n.strip()]
                for name in names:
                    name_emails.setdefault(name, set()).add(email)
                if len(names) == 1 and email:
                    sole_email.setdefault(names[0], email)

        # Second pass: create or look up User for each name
        users = {}
        for full_name in name_emails:
            user = User.objects.filter(full_name=full_name).first()
            if not user:
                email = sole_email.get(full_name)
                if not email or User.objects.filter(email=email).exists():
                    slug = full_name.lower().replace(" ", ".")
                    email = f"{slug}@cantorales-contributor.invalid"
                user = User.objects.create_user(
                    email=email,
                    full_name=full_name,
                    password=None,  # unusable password
                )
                self.stdout.write(f"  Created user: {full_name} <{email}>")
            users[full_name] = user
        return users
