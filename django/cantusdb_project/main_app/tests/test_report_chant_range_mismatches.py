import csv
import os
import tempfile
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from main_app.models import Chant, Sequence
from main_app.tests.make_fakes import make_fake_chant, make_fake_sequence


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

    def _make_mismatched_chant(self, volpiano: str, chant_range: str) -> Chant:
        """Create a chant whose stored chant_range disagrees with its volpiano.

        Saving derives the range from the volpiano, so the mismatch this report
        exists to find has to be forced in with a signal-free .update().
        """
        chant = make_fake_chant(volpiano=volpiano)
        Chant.objects.filter(pk=chant.pk).update(chant_range=chant_range)
        chant.refresh_from_db()
        return chant

    def test_lists_mismatched_chants_tagged_by_type(self):
        # all volpianos derive "1-c-g-4"; each stored range differs another way
        volpiano = "1---c--d--e--f--g---4"
        pitch = self._make_mismatched_chant(volpiano, "1-a-b-4")  # different ambitus
        # liquescent (uppercase) extreme, same pitches
        case = self._make_mismatched_chant(volpiano, "1-c-G-4")
        # malformed (missing dash), same pitches
        formatting = self._make_mismatched_chant(volpiano, "1c-g-4")
        # stored range matches its derived range -> not a mismatch
        make_fake_chant(volpiano=volpiano)
        # no volpiano -> nothing to derive, excluded
        make_fake_chant(volpiano=None, chant_range="1-a-b-4")

        rows = self._run_report()
        self.assertEqual(rows[0][-1], "difference_type")
        by_id = {row[1]: row for row in rows[1:]}

        self.assertEqual(len(by_id), 3)
        self.assertEqual(by_id[str(pitch.pk)][4:], ["1-a-b-4", "1-c-g-4", "pitch"])
        self.assertEqual(by_id[str(case.pk)][6], "case")
        self.assertEqual(by_id[str(formatting.pk)][6], "formatting")
        self.assertEqual(by_id[str(pitch.pk)][0], "chant")

    def test_mismatched_sequences_are_reported(self):
        # chant_range lives on BaseChant, so sequences can drift too. The report
        # backs up populate_chant_ranges --overwrite, which writes both models.
        sequence = make_fake_sequence()
        sequence.volpiano = "1---c--d--e---4"
        sequence.save()
        Sequence.objects.filter(pk=sequence.pk).update(chant_range="1-a-b-4")

        rows = self._run_report()
        sequence_rows = [row for row in rows[1:] if row[0] == "sequence"]

        self.assertEqual(len(sequence_rows), 1)
        self.assertEqual(sequence_rows[0][1], str(sequence.pk))
        self.assertEqual(sequence_rows[0][4:], ["1-a-b-4", "1-c-e-4", "pitch"])

    def test_report_mutates_nothing(self):
        mismatch = self._make_mismatched_chant("1---c--d--e--f--g---4", "1-a-b-4")
        self._run_report()
        mismatch.refresh_from_db()
        self.assertEqual(mismatch.chant_range, "1-a-b-4")

    def test_report_mutates_no_chant_in_a_diverse_population(self):
        # Every category the report can encounter must come through untouched:
        # each mismatch type, a matching row, a no-volpiano row, and a blank row.
        volpiano = "1---c--d--e--f--g---4"  # derives "1-c-g-4"
        self._make_mismatched_chant(volpiano, "1-a-b-4")  # pitch mismatch
        self._make_mismatched_chant(volpiano, "1-c-G-4")  # case mismatch
        self._make_mismatched_chant(volpiano, "1c-g-4")  # formatting mismatch
        make_fake_chant(volpiano=volpiano)  # matches derived
        make_fake_chant(volpiano=None, chant_range="1-a-b-4")  # no volpiano to derive
        make_fake_chant(volpiano=None, chant_range="")  # genuinely blank row

        before = dict(Chant.objects.values_list("id", "chant_range"))
        count_before = Chant.objects.count()

        self._run_report()

        after = dict(Chant.objects.values_list("id", "chant_range"))
        self.assertEqual(before, after)
        self.assertEqual(Chant.objects.count(), count_before)
