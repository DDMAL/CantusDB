import io
import tempfile
from unittest.mock import patch

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase

from main_app.management.commands.import_cantorales import parse_centuries
from main_app.models import Provenance, Source
from main_app.tests.make_fakes import (
    make_fake_century,
    make_fake_institution,
    make_fake_segment,
    make_fake_source,
)


class TestParseCenturies(TestCase):
    def test_empty(self):
        self.assertEqual(parse_centuries(""), [])

    def test_single(self):
        self.assertEqual(parse_centuries("16"), ["16th century"])

    def test_comma_separated(self):
        self.assertEqual(parse_centuries("16, 17"), ["16th century", "17th century"])

    def test_dash_range(self):
        self.assertEqual(
            parse_centuries("15-17"), ["15th century", "16th century", "17th century"]
        )

    def test_slash_separated(self):
        self.assertEqual(parse_centuries("16/17"), ["16th century", "17th century"])

    def test_ordinal_exceptions(self):
        # 11th, 12th, 13th use "th" not "st"/"nd"/"rd"
        self.assertEqual(parse_centuries("11"), ["11th century"])
        self.assertEqual(parse_centuries("12"), ["12th century"])
        self.assertEqual(parse_centuries("13"), ["13th century"])


# Minimal valid CSV content (header + REQUIRED + SAMPLE + 1 data row)
# Columns are 0-indexed; see COL_* constants in import_cantorales.py
def _make_csv(
    rism="US-NYcu",
    shelfmark="Ms. 1",
    contributor="Jane Doe",
    email="jane@example.com",
    origins="Franciscan",
):
    header = ",".join(
        [
            "col0",
            "RISM",
            "Shelfmark",
            "City",
            "Archive",
            "Condition",
            "Leaves",
            "Material",
            "SourceType",
            "ChantType",
            "Century",
            "Date",
            "Staves",
            "StaffLines",
            "Colophon",
            "Origins",
            "Owners",
            "TextScript",
            "Notation",
            "Binding",
            "Notes",
            "Images",
            "ArchiveLink",
            "CantusDBLink",
            "Contributor",
            "Email",
            "DateEntered",
            "SourceOfData",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    required = header  # same shape
    sample = header
    data = ",".join(
        [
            "",
            rism,
            shelfmark,
            "New York",
            "Columbia University",
            "1",
            "200",
            "2",
            "1",
            "2",
            "16",
            "1600",
            "5",
            "4",
            "1",
            origins,
            "",
            "",
            "",
            "",
            "",
            "http://example.com/img",
            "http://example.com/archive",
            "",
            contributor,
            email,
            "2024-01-01",
            "Database",
            "",
            "",
            "",
            "",
            "",
        ]
    )
    return "\n".join([header, required, sample, data])


class TestImportCantoralesCommand(TestCase):
    def setUp(self):
        make_fake_segment(
            name="Cantorales in the Americas and Beyond",
            id=settings.CANTORALES_SEGMENT_ID,
        )
        make_fake_century(name="16th century")

    def test_creates_source(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(_make_csv())
            csv_path = f.name

        with patch(
            "main_app.management.commands.import_cantorales.CSV_FILENAME",
            csv_path,
        ), patch(
            "main_app.management.commands.import_cantorales.os.path.join",
            return_value=csv_path,
        ):
            call_command("import_cantorales", stdout=io.StringIO())

        self.assertEqual(Source.objects.filter(shelfmark="Ms. 1").count(), 1)
        source = Source.objects.get(shelfmark="Ms. 1")
        self.assertTrue(source.published)
        self.assertIn(
            "Cantorales in the Americas and Beyond",
            source.segment_m2m.values_list("name", flat=True),
        )

    def test_provenance_fk_set_from_origins(self):
        """The 'Origins and History' value should create a Provenance entry and
        link it via the FK (not only provenance_notes), so it appears on the
        browse-sources page."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(_make_csv(origins="Franciscan"))
            csv_path = f.name

        with patch(
            "main_app.management.commands.import_cantorales.os.path.join",
            return_value=csv_path,
        ):
            call_command("import_cantorales", stdout=io.StringIO())

        source = Source.objects.get(shelfmark="Ms. 1")
        self.assertIsNotNone(source.provenance)
        self.assertEqual(source.provenance.name, "Franciscan")
        self.assertEqual(source.provenance_notes, "Franciscan")
        self.assertTrue(Provenance.objects.filter(name="Franciscan").exists())

    def test_provenance_no_value_leaves_fk_null(self):
        """An Origins value of 'no' should leave both the provenance FK and
        provenance_notes empty."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(_make_csv(origins="no"))
            csv_path = f.name

        with patch(
            "main_app.management.commands.import_cantorales.os.path.join",
            return_value=csv_path,
        ):
            call_command("import_cantorales", stdout=io.StringIO())

        source = Source.objects.get(shelfmark="Ms. 1")
        self.assertIsNone(source.provenance)
        self.assertIsNone(source.provenance_notes)

    def test_does_not_overwrite_existing_source(self):
        """Regression test for issue #2059.

        When a source already exists in CDB with the same holding institution
        and shelfmark as a CSV row, the import must leave it completely
        untouched: curated scalar fields are preserved, no unexpected editor is
        added, and the Cantorales segment is not attached.
        """
        institution = make_fake_institution(siglum="US-NYcu", country="United States")
        source = make_fake_source(
            holding_institution=institution,
            shelfmark="Ms. 1",
            description="Curated description, do not touch",
            provenance_notes="Curated provenance note",
            published=False,
            segment_name="CANTUS Database",
        )
        original_description = source.description
        original_provenance_notes = source.provenance_notes
        original_provenance_id = source.provenance_id
        original_contributor_ids = set(
            source.source_data_contributed_by.values_list("id", flat=True)
        )
        original_inventoried_ids = set(
            source.inventoried_by.values_list("id", flat=True)
        )

        # CSV row collides on (US-NYcu, Ms. 1) and carries different data plus a
        # new contributor ("Jane Doe").
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(_make_csv())
            csv_path = f.name

        with patch(
            "main_app.management.commands.import_cantorales.os.path.join",
            return_value=csv_path,
        ):
            call_command("import_cantorales", stdout=io.StringIO())

        source.refresh_from_db()

        # Scalar fields untouched.
        self.assertEqual(source.description, original_description)
        self.assertEqual(source.provenance_notes, original_provenance_notes)
        self.assertEqual(source.provenance_id, original_provenance_id)
        self.assertFalse(source.published)

        # No editor was added or removed (the CSV's "Jane Doe" must not appear).
        self.assertEqual(
            set(source.source_data_contributed_by.values_list("id", flat=True)),
            original_contributor_ids,
        )
        self.assertEqual(
            set(source.inventoried_by.values_list("id", flat=True)),
            original_inventoried_ids,
        )
        self.assertNotIn(
            "Jane Doe",
            source.source_data_contributed_by.values_list("full_name", flat=True),
        )

        # The Cantorales segment was not attached to the pre-existing source.
        self.assertNotIn(
            settings.CANTORALES_SEGMENT_ID,
            source.segment_m2m.values_list("pk", flat=True),
        )

        # No duplicate source was created.
        self.assertEqual(Source.objects.filter(shelfmark="Ms. 1").count(), 1)

    def test_idempotent(self):
        """Running the command twice should not create duplicate sources."""
        institution = make_fake_institution(siglum="US-NYcu", country="United States")

        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as f:
            f.write(_make_csv())
            csv_path = f.name

        with patch(
            "main_app.management.commands.import_cantorales.os.path.join",
            return_value=csv_path,
        ):
            call_command("import_cantorales", stdout=io.StringIO())
            call_command("import_cantorales", stdout=io.StringIO())

        self.assertEqual(Source.objects.filter(shelfmark="Ms. 1").count(), 1)
