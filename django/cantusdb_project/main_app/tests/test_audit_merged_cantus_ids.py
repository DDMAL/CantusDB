import csv
import os
import tempfile
from io import StringIO
from unittest.mock import MagicMock, patch

import requests
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from cantusindex import get_merged_cantus_ids
from main_app.management.commands.audit_merged_cantus_ids import (
    follow,
    read_merges,
)
from main_app.models import Chant
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_sequence,
    make_fake_source,
)

FETCH = "main_app.management.commands.audit_merged_cantus_ids.get_merged_cantus_ids"

MERGES = [
    {"id": "1", "old": "000100", "new": "000200", "date": "2026-01-01"},
    # merged twice in a row: 000300 → 000400 → 000500
    {"id": "2", "old": "000300", "new": "000400", "date": "2025-01-01"},
    {"id": "3", "old": "000400", "new": "000500", "date": "2026-02-01"},
    # merged into two different IDs
    {"id": "4", "old": "g01114", "new": "g00717", "date": "2026-03-01"},
    {"id": "5", "old": "g01114", "new": "g05858", "date": "2026-03-02"},
]


class ReadMergesTest(SimpleTestCase):
    def test_follows_later_merges(self):
        merges = read_merges(MERGES)
        self.assertEqual(follow("000100", merges), (["000100", "000200"], ""))
        self.assertEqual(follow("000300", merges), (["000300", "000400", "000500"], ""))

    def test_an_id_merged_into_two_needs_a_decision(self):
        chain, note = follow("g01114", read_merges(MERGES))
        self.assertEqual(chain, ["g01114"])
        self.assertIn("more than one ID (g00717, g05858)", note)

    def test_stops_at_a_loop(self):
        merges = read_merges(
            [{"old": "000001", "new": "000002"}, {"old": "000002", "new": "000001"}]
        )
        self.assertEqual(follow("000001", merges)[1], "the merges form a loop")

    def test_skips_events_without_two_different_ids(self):
        merges = read_merges(
            [
                {"old": "", "new": "000002"},
                {"old": "000003", "new": None},
                {"old": "000004", "new": "000004"},
                "not a merge",
            ]
        )
        self.assertEqual(merges, {})


class AuditMergedCantusIdsCommandTest(TestCase):
    def run_audit(self, *args):
        out = StringIO()
        with patch(FETCH, return_value=MERGES):
            call_command("audit_merged_cantus_ids", *args, stdout=out)
        return out.getvalue()

    def test_lists_records_using_a_merged_id_and_changes_nothing(self):
        source = make_fake_source(published=True)
        merged = make_fake_chant(source=source, cantus_id="000100")
        chained = make_fake_chant(source=source, cantus_id="000300")
        current = make_fake_chant(source=source, cantus_id="000200")
        sequence = make_fake_sequence(source=source, cantus_id="000100")

        output = self.run_audit()

        self.assertIn("000100 → 000200", output)
        self.assertIn("000300 → 000500 (via 000300 → 000400 → 000500)", output)
        self.assertIn(
            f"source {source.id} ({source.short_heading}): 1 chant, 1 sequence", output
        )
        self.assertNotIn("000200 →", output, "an ID that wasn't merged isn't listed")
        self.assertIn("2 chant(s) and 1 sequence(s) in 1 source(s)", output)
        for record, cantus_id in [
            (merged, "000100"),
            (chained, "000300"),
            (current, "000200"),
            (sequence, "000100"),
        ]:
            record.refresh_from_db()
            self.assertEqual(record.cantus_id, cantus_id)

    def test_an_id_merged_into_two_is_listed_for_a_decision(self):
        make_fake_chant(cantus_id="g01114")
        output = self.run_audit()
        decision = output.index("Need a decision")
        self.assertIn(
            "g01114 g01114 was merged into more than one ID", output[decision:]
        )

    def test_marks_unpublished_sources(self):
        source = make_fake_source(published=False)
        make_fake_chant(source=source, cantus_id="000100")
        self.assertIn(f"({source.short_heading}, unpublished)", self.run_audit())

    def test_only_one_source(self):
        wanted = make_fake_chant(cantus_id="000100")
        other = make_fake_chant(cantus_id="000100")
        output = self.run_audit("--source", str(wanted.source_id))
        self.assertIn(f"source {wanted.source_id} ", output)
        self.assertNotIn(f"source {other.source_id} ", output)

    def test_writes_a_csv_row_per_record(self):
        chant = make_fake_chant(cantus_id="000300", folio="012r", c_sequence=3)
        make_fake_chant(cantus_id="g01114")
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "merged.csv")
            self.run_audit("--csv", path)
            with open(path, encoding="utf-8") as csv_file:
                rows = {row["cantus_id"]: row for row in csv.DictReader(csv_file)}
        self.assertEqual(rows["000300"]["id"], str(chant.id))
        self.assertEqual(rows["000300"]["folio"], "012r")
        self.assertEqual(rows["000300"]["order"], "3")
        self.assertEqual(rows["000300"]["new_cantus_id"], "000500")
        self.assertEqual(rows["000300"]["chain"], "000300 → 000400 → 000500")
        self.assertEqual(rows["g01114"]["new_cantus_id"], "", "someone has to choose")
        self.assertIn("more than one ID", rows["g01114"]["note"])

    def test_nothing_to_report(self):
        make_fake_chant(cantus_id="000200")
        self.assertIn(
            "No chants or sequences use a merged Cantus ID.", self.run_audit()
        )

    def test_cantus_index_unavailable(self):
        with patch(FETCH, return_value=None):
            with self.assertRaises(CommandError):
                call_command("audit_merged_cantus_ids", stdout=StringIO())
        self.assertEqual(Chant.objects.count(), 0)


class GetMergedCantusIdsTest(SimpleTestCase):
    @patch("cantusindex.requests.get", side_effect=requests.ConnectionError)
    def test_connection_error(self, _get):
        self.assertIsNone(get_merged_cantus_ids())

    @patch("cantusindex.requests.get")
    def test_invalid_json(self, get):
        get.return_value = MagicMock(status_code=200, text="<html>error</html>")
        self.assertIsNone(get_merged_cantus_ids())

    @patch("cantusindex.requests.get")
    def test_passes_the_timeout(self, get):
        get.return_value = MagicMock(status_code=200, text="[]")
        get_merged_cantus_ids(timeout=60)
        self.assertEqual(get.call_args.kwargs["timeout"], 60)
