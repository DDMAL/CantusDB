from io import StringIO

from django.core.management import call_command
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
