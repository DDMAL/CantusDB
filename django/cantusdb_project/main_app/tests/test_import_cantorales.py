import io
import tempfile
import textwrap
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from main_app.management.commands.import_cantorales import parse_centuries
from main_app.models import Source
from main_app.tests.make_fakes import (
    make_fake_century,
    make_fake_institution,
    make_fake_segment,
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
    rism="US-NYcu", shelfmark="Ms. 1", contributor="Jane Doe", email="jane@example.com"
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
            "Franciscan",
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
        make_fake_segment(name="Cantorales in the Americas", id=4067)
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
            "Cantorales in the Americas",
            source.segment_m2m.values_list("name", flat=True),
        )

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
