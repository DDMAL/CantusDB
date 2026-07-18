import csv
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from main_app.models import Chant
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

    def test_lists_mismatched_chants_tagged_by_type(self):
        # all volpianos derive "1-c-g-4"; each stored range differs another way
        pitch = make_fake_chant(
            volpiano="1---c--d--e--f--g---4", chant_range="1-a-b-4"
        )  # different ambitus
        case = make_fake_chant(
            volpiano="1---c--d--e--f--g---4", chant_range="1-c-G-4"
        )  # liquescent (uppercase) extreme, same pitch
        formatting = make_fake_chant(
            volpiano="1---c--d--e--f--g---4", chant_range="1c-g-4"
        )  # malformed (missing dash), same pitches
        # stored range matches its derived range -> not a mismatch
        make_fake_chant(volpiano="1---c--d--e--f--g---4", chant_range="1-c-g-4")
        # no volpiano -> nothing to derive, excluded
        make_fake_chant(volpiano=None, chant_range="1-a-b-4")

        rows = self._run_report()
        self.assertEqual(rows[0][-1], "difference_type")
        by_id = {row[0]: row for row in rows[1:]}

        self.assertEqual(len(by_id), 3)
        self.assertEqual(by_id[str(pitch.id)][3:], ["1-a-b-4", "1-c-g-4", "pitch"])
        self.assertEqual(by_id[str(case.id)][5], "case")
        self.assertEqual(by_id[str(formatting.id)][5], "formatting")

    def test_report_mutates_nothing(self):
        mismatch = make_fake_chant(
            volpiano="1---c--d--e--f--g---4", chant_range="1-a-b-4"
        )
        self._run_report()
        mismatch.refresh_from_db()
        self.assertEqual(mismatch.chant_range, "1-a-b-4")

    def test_report_mutates_no_chant_in_a_diverse_population(self):
        # Every category the report can encounter must come through untouched:
        # each mismatch type, a matching row, a no-volpiano row, and a blank row.
        volpiano = "1---c--d--e--f--g---4"  # derives "1-c-g-4"
        make_fake_chant(volpiano=volpiano, chant_range="1-a-b-4")  # pitch mismatch
        make_fake_chant(volpiano=volpiano, chant_range="1-c-G-4")  # case mismatch
        make_fake_chant(volpiano=volpiano, chant_range="1c-g-4")  # formatting mismatch
        make_fake_chant(volpiano=volpiano, chant_range="1-c-g-4")  # matches derived
        make_fake_chant(volpiano=None, chant_range="1-a-b-4")  # no volpiano to derive
        make_fake_chant(volpiano=None, chant_range="")  # genuinely blank row

        before = dict(Chant.objects.values_list("id", "chant_range"))
        count_before = Chant.objects.count()

        self._run_report()

        after = dict(Chant.objects.values_list("id", "chant_range"))
        self.assertEqual(before, after)
        self.assertEqual(Chant.objects.count(), count_before)
