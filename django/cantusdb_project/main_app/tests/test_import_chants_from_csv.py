import io
import tempfile

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from main_app.models import Chant
from main_app.tests.make_fakes import (
    make_fake_feast,
    make_fake_source,
)

User = get_user_model()

def _write_csv(content: str) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".csv", delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name


def _run(path: str, dry_run: bool = False) -> str:
    out = io.StringIO()
    call_command("import_chants_from_csv", path, dry_run=dry_run, stdout=out)
    return out.getvalue()


class TestAtomicity(TestCase):
    """All rows must succeed or the entire import is rolled back."""

    def setUp(self):
        self.source = make_fake_source()

    def test_nonexistent_source_id_rolls_back_all_chants(self):
        csv = (
            "source_id,folio,sequence,incipit\n"
            f"{self.source.id},001r,1,Kyrie\n"
            "9999999,001r,2,Gloria\n"
        )
        with self.assertRaises(CommandError):
            _run(_write_csv(csv))
        self.assertEqual(Chant.objects.filter(source=self.source).count(), 0)

    def test_invalid_sequence_rolls_back_all_chants(self):
        csv = (
            "source_id,folio,sequence,incipit\n"
            f"{self.source.id},001r,1,Kyrie\n"
            f"{self.source.id},001r,not-a-number,Gloria\n"
        )
        with self.assertRaises(CommandError):
            _run(_write_csv(csv))
        self.assertEqual(Chant.objects.filter(source=self.source).count(), 0)


class TestFKEdgeCases(TestCase):
    """FK lookups: empty values, caching, and correct resolution."""

    def setUp(self):
        User.objects.create(id=1)
        self.source = make_fake_source()
        self.feast = make_fake_feast(name="Dom. 1 Adventus")

    def test_empty_feast_cell_saves_none(self):
        csv = f"source_id,folio,sequence,feast\n{self.source.id},001r,1,\n"
        _run(_write_csv(csv))
        chant = Chant.objects.get(source=self.source)
        self.assertIsNone(chant.feast)

    def test_repeated_feast_value_hits_db_only_once(self):
        # The cache should prevent redundant lookups, only one query to resolve the feast for all 10 rows
        rows = "\n".join(
            f"{self.source.id},{str(i).zfill(3)}r,1,Dom. 1 Adventus"
            for i in range(1, 11)
        )
        csv = f"source_id,folio,sequence,feast\n{rows}\n"
        with CaptureQueriesContext(connection) as ctx:
            _run(_write_csv(csv))
        # Exclude FK integrity checks (SELECT 1 AS "a" FROM ...) fired by Django on INSERT
        feast_lookups = [
            q for q in ctx.captured_queries
            if "main_app_feast" in q["sql"]
            and "SELECT" in q["sql"]
            and "1 AS" not in q["sql"]
        ]
        self.assertEqual(len(feast_lookups), 1)

    def test_source_id_resolves_to_correct_source(self):
        csv = f"source_id,folio,sequence\n{self.source.id},001r,1\n"
        _run(_write_csv(csv))
        chant = Chant.objects.get(source=self.source)
        self.assertEqual(chant.source, self.source)


class TestProofreadBooleans(TestCase):
    """Proofread columns: 1→True, 0→False, empty→None, other→error."""

    def setUp(self):
        User.objects.create(id=1)
        self.source = make_fake_source()

    def test_proofread_values_parsed_correctly(self):
        csv = (
            "source_id,folio,sequence,"
            "fulltext_standardized_proofread,fulltext_ms_proofread,volpiano_proofread\n"
            f"{self.source.id},001r,1,1,0,\n"
        )
        _run(_write_csv(csv))
        chant = Chant.objects.get(source=self.source)
        self.assertTrue(chant.manuscript_full_text_std_proofread)
        self.assertFalse(chant.manuscript_full_text_proofread)
        self.assertIsNone(chant.volpiano_proofread)

    def test_invalid_proofread_value_stores_null_with_warning(self):
        csv = (
            "source_id,folio,sequence,volpiano_proofread\n"
            f"{self.source.id},001r,1,yes\n"
        )
        output = _run(_write_csv(csv))
        chant = Chant.objects.get(source=self.source)
        self.assertIsNone(chant.volpiano_proofread)
        self.assertIn("storing NULL", output)
