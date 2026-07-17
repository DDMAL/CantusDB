import csv
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from main_app.tests.make_fakes import make_fake_chant


class TestReportChantRangeMismatches(TestCase):
    def _run_report(self) -> list[list[str]]:
        """Run the report to a temp CSV and return its rows (including header)."""
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            call_command(
                "report_chant_range_mismatches", output=path, stderr=StringIO()
            )
            with open(path, newline="", encoding="utf-8") as report:
                return list(csv.reader(report))
        finally:
            os.remove(path)

    def test_lists_only_mismatched_chants(self):
        # stored range disagrees with the range derived from the volpiano
        mismatch = make_fake_chant(
            volpiano="1---c--d--e--f--g---4", chant_range="1-a-b-4"
        )
        # stored range matches its derived range -> not a mismatch
        make_fake_chant(volpiano="1---c--d--e--f--g---4", chant_range="1-c-g-4")
        # no volpiano -> nothing to derive, excluded
        make_fake_chant(volpiano=None, chant_range="1-a-b-4")

        rows = self._run_report()
        data_rows = rows[1:]

        self.assertEqual(len(data_rows), 1)
        row = data_rows[0]
        self.assertEqual(row[0], str(mismatch.id))
        self.assertEqual(row[3], "1-a-b-4")  # stored
        self.assertEqual(row[4], "1-c-g-4")  # derived

    def test_report_mutates_nothing(self):
        mismatch = make_fake_chant(
            volpiano="1---c--d--e--f--g---4", chant_range="1-a-b-4"
        )
        self._run_report()
        mismatch.refresh_from_db()
        self.assertEqual(mismatch.chant_range, "1-a-b-4")
