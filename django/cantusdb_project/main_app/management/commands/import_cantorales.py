"""
Management command to import sources from the "cantorales_2024-05-01.csv"
spreadsheet into CantusDB.

Sources are tagged with the Cantorales segment (settings.CANTORALES_SEGMENT_ID)
so they appear on /Cantorales/ but NOT on /sources/?segment=4063 (CANTUS Database).

The command only ever creates sources: a CSV row matching a source that already
exists is logged and skipped, never updated (issue #2059). It is therefore safe
to re-run, and a skipped row leaves nothing behind — no Source, no Institution,
and no contributor User.
"""

import csv
import os
import re
from typing import Any, Optional

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
import reversion  # type: ignore[import-untyped]

from main_app.models import (
    Century,
    Institution,
    Segment,
    Source,
)
from main_app.models.source_url import SourceURL
from users.models import User


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


def ordinal(n: int) -> str:
    """Return e.g. '16th' for 16."""
    if 11 <= n % 100 <= 13:
        return f"{n:02d}th"
    return f"{n:02d}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")


def parse_centuries(raw: str) -> list[str]:
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


def build_description(row: list[str]) -> str:
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
    def handle(self, *args: Any, **options: Any) -> None:
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

        cantorales_segment = Segment.objects.filter(
            pk=settings.CANTORALES_SEGMENT_ID
        ).first()
        if cantorales_segment is None:
            self.stderr.write(
                f"Cantorales segment (pk={settings.CANTORALES_SEGMENT_ID}) "
                "not found; aborting."
            )
            return

        # Pre-fetch century lookup
        century_by_name = {c.name: c for c in Century.objects.all()}

        # Resolve the best email for each contributor name. This is a read-only
        # pass over the whole CSV: the accounts themselves are created lazily,
        # per row, once the row is known to be importable.
        contributor_emails = self._read_contributor_emails(csv_path)
        contributor_users: dict[str, User] = {}

        created_count = 0
        skipped_existing_count = 0
        skipped_count = 0
        institution_created_count = 0
        user_created_count = 0

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
                # Look the institution up without creating it. Creation is
                # deferred until the row is known to be importable, so a row
                # that turns out to duplicate an existing source can never leave
                # a stray Institution behind.
                institution = (
                    Institution.objects.filter(siglum=rism).first() if rism else None
                )

                # --- Skip existing sources entirely (issue #2059) ---
                # An earlier version of this import used update_or_create, which
                # overwrote curated metadata and added unexpected editors on
                # sources that already existed in CDB. We now refuse to modify
                # any existing source: if one already matches we skip the row.
                #
                # How we match depends on whether the row names an institution:
                #
                # * With a RISM siglum, (holding_institution, shelfmark)
                #   identifies a source, so we check the whole database — the
                #   sources we must not touch (HRC 145 and friends) are curated
                #   sources living outside the Cantorales segment.
                # * Without one, all we have is a shelfmark, which is not
                #   evidence of identity by itself: unrelated institution-less
                #   sources routinely share shelfmarks. Matching those across the
                #   whole database would silently drop rows that should have been
                #   imported, so we only dedupe against sources this import
                #   created previously, which still keeps re-runs idempotent.
                #
                # An institution that doesn't exist yet has no sources, so that
                # case needs no query at all.
                if rism and institution is None:
                    already_exists = False
                elif institution is not None:
                    already_exists = Source.objects.filter(
                        holding_institution=institution, shelfmark=shelfmark
                    ).exists()
                else:
                    already_exists = Source.objects.filter(
                        holding_institution__isnull=True,
                        shelfmark=shelfmark,
                        segment_m2m=cantorales_segment,
                    ).exists()

                if already_exists:
                    skipped_existing_count += 1
                    existing_label = (
                        f"{institution} {shelfmark}" if institution else shelfmark
                    )
                    self.stdout.write(
                        f"  Row {row_num}: SKIP — source already exists, leaving "
                        f"it untouched: {existing_label}"
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
                # Stored as a SourceURL, not Source.image_link: that field is
                # being retired (#1818, #1839) and source_detail.html only
                # renders source_links, so an image_link value would never
                # reach the page.
                image_link = row[COL_IMAGES].strip()

                # --- Indexing date (from "Date data entered") ---
                indexing_date = row[COL_DATE_ENTERED].strip() or None

                # --- Indexing notes (from "Source of data entered") ---
                source_of_data = row[COL_SOURCE_OF_DATA].strip()
                indexing_notes = (
                    f"Source of data: {source_of_data}" if source_of_data else None
                )

                # --- Create the new Source and everything attached to it in a
                # single reversion revision. Management-command writes bypass
                # RevisionMiddleware, so we wrap them explicitly to keep the
                # import auditable (issue #2059 was about undetected changes). ---
                with reversion.create_revision():
                    # The row is definitely being imported now, so it's safe to
                    # create the holding institution it referred to.
                    if rism and institution is None:
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

                    source = Source.objects.create(
                        holding_institution=institution,
                        shelfmark=shelfmark,
                        source_completeness=completeness,
                        provenance_notes=provenance_notes,
                        date=date,
                        description=description or None,
                        indexing_date=indexing_date,
                        indexing_notes=indexing_notes,
                        source_status="Unpublished / No indexing activity",
                        published=True,
                    )

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

                    # --- Images → SourceURL ---
                    if image_link:
                        SourceURL.objects.get_or_create(
                            source=source,
                            url=image_link,
                            defaults={
                                "url_type": SourceURL.URLTypes.EXTERNAL_IMAGES,
                            },
                        )

                    # --- Link contributor users ---
                    # Accounts are created here rather than up front so a
                    # skipped row leaves no stub User behind, matching the
                    # deferred Institution creation above.
                    contributor_raw = row[COL_CONTRIBUTOR].strip()
                    if contributor_raw:
                        for name in re.split(r",\s*", contributor_raw):
                            name = name.strip()
                            if not name:
                                continue
                            user = contributor_users.get(name)
                            if user is None:
                                user, was_created = self._get_or_create_contributor(
                                    name, contributor_emails.get(name)
                                )
                                contributor_users[name] = user
                                user_created_count += was_created
                            source.source_data_contributed_by.add(user)

                    reversion.set_comment("import_cantorales: issue #2059")

                created_count += 1
                self.stdout.write(f"  Created source: {source} (row {row_num})")

        self.stdout.write("")
        self.stdout.write(
            f"Done. Created {created_count}, "
            f"skipped {skipped_existing_count} already-existing, "
            f"skipped {skipped_count} invalid. "
            f"New institutions: {institution_created_count}. "
            f"New users: {user_created_count}."
        )

    def _read_contributor_emails(self, csv_path: str) -> dict[str, str]:
        """
        Return {full_name: email} for contributors the CSV gives an email for.

        The CSV often lists multiple people in one contributor field
        ("Victor Williams, Milton Gomez") with a single shared email, which
        tells us nothing about which address belongs to whom. Only a row where
        someone is the *sole* contributor identifies their email, so that is
        the only case recorded here; everyone else gets a .invalid placeholder
        at creation time.

        This pass reads the whole CSV but writes nothing: a name may appear on
        several rows, and we need the sole-contributor row to resolve an email
        even when a different row is the one being imported.
        """
        sole_email: dict[str, str] = {}
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
                if len(names) == 1 and email:
                    sole_email.setdefault(names[0], email)
        return sole_email

    def _get_or_create_contributor(
        self, full_name: str, email: Optional[str]
    ) -> tuple[User, bool]:
        """
        Look up the contributor by name, creating a stub account (unusable
        password) if they have none. Returns (user, was_created).
        """
        user = User.objects.filter(full_name=full_name).first()
        if user is not None:
            return user, False

        if not email or User.objects.filter(email=email).exists():
            slug = full_name.lower().replace(" ", ".")
            email = f"{slug}@cantorales-contributor.invalid"
        user = User.objects.create_user(
            email=email,
            full_name=full_name,
            password=None,  # unusable password
        )
        self.stdout.write(f"  Created user: {full_name} <{email}>")
        return user, True
