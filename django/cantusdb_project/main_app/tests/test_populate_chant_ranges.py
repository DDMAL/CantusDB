from io import StringIO

from django.core.management import call_command
from django.forms.models import model_to_dict
from django.test import TestCase

from main_app.models import Chant, Sequence
from main_app.tests.make_fakes import make_fake_chant, make_fake_sequence


class TestPopulateChantRanges(TestCase):
    def _make_legacy_chant(self, volpiano: str, chant_range: str) -> Chant:
        """Create a chant whose stored chant_range disagrees with its volpiano.

        Saving derives the range from the volpiano, so a mismatch (or a blank)
        has to be forced back in with a signal-free .update() to mimic the
        pre-existing rows this command exists to fix.
        """
        chant = make_fake_chant(volpiano=volpiano)
        Chant.objects.filter(pk=chant.pk).update(chant_range=chant_range)
        chant.refresh_from_db()
        return chant

    def _make_legacy_blank_range_chant(self, volpiano: str) -> Chant:
        return self._make_legacy_chant(volpiano, "")

    def test_blank_ranges_are_filled(self):
        chant = self._make_legacy_blank_range_chant("1---c--d--e--f--g---4")
        call_command("populate_chant_ranges", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-c-g-4")

    def test_existing_ranges_are_preserved_by_default(self):
        # Without --overwrite the command only ever fills blanks, so a legacy
        # mismatch survives the run untouched.
        chant = self._make_legacy_chant("1---c--d--e--f--g---4", "1-a-b-4")
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

    def test_variety_of_existing_values_are_preserved_by_default(self):
        # None of these non-blank ranges may be overwritten without --overwrite,
        # however they compare to the derived "1-c-g-4".
        volpiano = "1---c--d--e--f--g---4"
        cases = {
            "plainly wrong ambitus": "1-a-b-4",
            "uppercase liquescent extreme": "1-c-G-4",
            "malformed (missing dash)": "1c-g-4",
        }
        chants = {
            label: self._make_legacy_chant(volpiano, stored)
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
        self.assertIn("1 chants", out.getvalue())

        out = StringIO()
        call_command("populate_chant_ranges", stdout=out)
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-c-e-4")
        self.assertIn("0 chants", out.getvalue())

    def test_preexisting_chant_is_byte_identical_after_default_run(self):
        # A non-blank chant must come out of a default run completely unchanged.
        chant = self._make_legacy_chant("1---c--d--e---4", "1-a-b-4")
        before = model_to_dict(Chant.objects.get(pk=chant.pk))
        call_command("populate_chant_ranges", stdout=StringIO())
        after = model_to_dict(Chant.objects.get(pk=chant.pk))
        self.assertEqual(before, after)

    def test_fill_touches_only_chant_range(self):
        # A backfilled chant changes in chant_range and nothing else.
        chant = self._make_legacy_blank_range_chant("1---c--d--e---4")
        before = model_to_dict(Chant.objects.get(pk=chant.pk))
        call_command("populate_chant_ranges", stdout=StringIO())
        after = model_to_dict(Chant.objects.get(pk=chant.pk))
        self.assertEqual(after["chant_range"], "1-c-e-4")
        before.pop("chant_range")
        after.pop("chant_range")
        self.assertEqual(before, after)


class TestPopulateChantRangesOverwrite(TestCase):
    """--overwrite is the opt-in that repairs legacy mismatches (#2081 / #1176)."""

    def _make_legacy_chant(self, volpiano: str, chant_range: str) -> Chant:
        chant = make_fake_chant(volpiano=volpiano)
        Chant.objects.filter(pk=chant.pk).update(chant_range=chant_range)
        chant.refresh_from_db()
        return chant

    def test_mismatched_range_is_replaced(self):
        chant = self._make_legacy_chant("1---c--d--e--f--g---4", "1-a-b-4")
        call_command("populate_chant_ranges", "--overwrite", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-c-g-4")

    def test_blank_ranges_are_still_filled(self):
        chant = self._make_legacy_chant("1---c--d--e---4", "")
        call_command("populate_chant_ranges", "--overwrite", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-c-e-4")

    def test_matching_ranges_are_not_counted_or_rewritten(self):
        # A row that already agrees with its melody is skipped, so the reported
        # count reflects real repairs rather than every chant with volpiano.
        chant = make_fake_chant(volpiano="1---c--d--e---4")
        self.assertEqual(chant.chant_range, "1-c-e-4")
        out = StringIO()
        call_command("populate_chant_ranges", "--overwrite", stdout=out)
        self.assertIn("0 chants", out.getvalue())

    def test_underivable_range_leaves_a_stored_value_alone(self):
        # A mid-melody clef change yields no range, so there is nothing to write
        # and the stored value is left as the only information available.
        chant = self._make_legacy_chant("1---c--2---c---4", "1-a-b-4")
        call_command("populate_chant_ranges", "--overwrite", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")

    def test_dry_run_counts_without_writing(self):
        chant = self._make_legacy_chant("1---c--d--e--f--g---4", "1-a-b-4")
        out = StringIO()
        call_command("populate_chant_ranges", "--overwrite", "--dry-run", stdout=out)
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")
        self.assertIn("1 chants", out.getvalue())
        self.assertIn("would be updated", out.getvalue())

    def test_overwrite_touches_only_chant_range(self):
        chant = self._make_legacy_chant("1---c--d--e---4", "1-a-b-4")
        before = model_to_dict(Chant.objects.get(pk=chant.pk))
        call_command("populate_chant_ranges", "--overwrite", stdout=StringIO())
        after = model_to_dict(Chant.objects.get(pk=chant.pk))
        self.assertEqual(after["chant_range"], "1-c-e-4")
        before.pop("chant_range")
        after.pop("chant_range")
        self.assertEqual(before, after)


class TestPopulateChantRangesSequences(TestCase):
    """chant_range lives on BaseChant, so the backfill covers sequences too."""

    def _make_legacy_sequence(self, volpiano: str, chant_range: str) -> Sequence:
        sequence = make_fake_sequence()
        sequence.volpiano = volpiano
        sequence.save()
        Sequence.objects.filter(pk=sequence.pk).update(chant_range=chant_range)
        sequence.refresh_from_db()
        return sequence

    def test_blank_sequence_range_is_filled(self):
        sequence = self._make_legacy_sequence("1---c--d--e---4", "")
        out = StringIO()
        call_command("populate_chant_ranges", stdout=out)
        sequence.refresh_from_db()
        self.assertEqual(sequence.chant_range, "1-c-e-4")
        self.assertIn("1 sequences", out.getvalue())

    def test_mismatched_sequence_range_survives_a_default_run(self):
        sequence = self._make_legacy_sequence("1---c--d--e---4", "1-a-b-4")
        call_command("populate_chant_ranges", stdout=StringIO())
        sequence.refresh_from_db()
        self.assertEqual(sequence.chant_range, "1-a-b-4")

    def test_mismatched_sequence_range_is_replaced_with_overwrite(self):
        sequence = self._make_legacy_sequence("1---c--d--e---4", "1-a-b-4")
        call_command("populate_chant_ranges", "--overwrite", stdout=StringIO())
        sequence.refresh_from_db()
        self.assertEqual(sequence.chant_range, "1-c-e-4")
