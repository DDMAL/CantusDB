from io import StringIO

from django.core.management import call_command
from django.forms.models import model_to_dict
from django.test import TestCase

from main_app.models import Chant
from main_app.tests.make_fakes import make_fake_chant


class TestPopulateChantRanges(TestCase):
    def _make_legacy_blank_range_chant(self, volpiano: str) -> Chant:
        """Create a chant with volpiano but a blank chant_range in the DB.

        The save signal auto-fills a blank range, so we force it back to blank
        with a signal-free .update() to mimic a pre-existing (legacy) row.
        """
        chant = make_fake_chant(volpiano=volpiano, chant_range="")
        Chant.objects.filter(id=chant.id).update(chant_range="")
        return chant

    def test_blank_ranges_are_filled(self):
        chant = self._make_legacy_blank_range_chant("1---c--d--e--f--g---4")
        call_command("populate_chant_ranges", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-c-g-4")

    def test_existing_ranges_are_preserved(self):
        chant = make_fake_chant(volpiano="1---c--d--e--f--g---4", chant_range="1-a-b-4")
        call_command("populate_chant_ranges", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")

    def test_no_volpiano_is_ignored(self):
        chant = make_fake_chant(volpiano=None, chant_range="")
        call_command("populate_chant_ranges", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "")

    def test_dry_run_writes_nothing(self):
        chant = self._make_legacy_blank_range_chant("1---c--d--e--f--g---4")
        call_command("populate_chant_ranges", "--dry-run", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "")

    def test_variety_of_existing_values_are_preserved(self):
        # None of these non-blank ranges may be overwritten, however they
        # compare to the derived "1-c-g-4".
        volpiano = "1---c--d--e--f--g---4"
        cases = {
            "plainly wrong ambitus": "1-a-b-4",
            "uppercase liquescent extreme": "1-c-G-4",
            "malformed (missing dash)": "1c-g-4",
        }
        chants = {
            label: make_fake_chant(volpiano=volpiano, chant_range=stored)
            for label, stored in cases.items()
        }
        call_command("populate_chant_ranges", stdout=StringIO())
        for label, chant in chants.items():
            with self.subTest(case=label):
                chant.refresh_from_db()
                self.assertEqual(chant.chant_range, cases[label])

    def test_junk_only_volpiano_stays_blank(self):
        # No derivable pitch -> nothing written, the row stays blank.
        chant = self._make_legacy_blank_range_chant("1---|[]*---4")
        call_command("populate_chant_ranges", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "")

    def test_second_run_is_a_no_op(self):
        chant = self._make_legacy_blank_range_chant("1---c--d--e---4")
        out = StringIO()
        call_command("populate_chant_ranges", stdout=out)
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-c-e-4")
        self.assertIn("1 chants updated", out.getvalue())

        out = StringIO()
        call_command("populate_chant_ranges", stdout=out)
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-c-e-4")
        self.assertIn("0 chants updated", out.getvalue())

    def test_preexisting_chant_is_byte_identical_after_run(self):
        # A non-blank chant must come out of a run completely unchanged.
        chant = make_fake_chant(volpiano="1---c--d--e---4", chant_range="1-a-b-4")
        before = model_to_dict(Chant.objects.get(id=chant.id))
        call_command("populate_chant_ranges", stdout=StringIO())
        after = model_to_dict(Chant.objects.get(id=chant.id))
        self.assertEqual(before, after)

    def test_fill_touches_only_chant_range(self):
        # A backfilled chant changes in chant_range and nothing else.
        chant = self._make_legacy_blank_range_chant("1---c--d--e---4")
        before = model_to_dict(Chant.objects.get(id=chant.id))
        call_command("populate_chant_ranges", stdout=StringIO())
        after = model_to_dict(Chant.objects.get(id=chant.id))
        self.assertEqual(after["chant_range"], "1-c-e-4")
        before.pop("chant_range")
        after.pop("chant_range")
        self.assertEqual(before, after)
