"""Tests for the merge_duplicate_differentiae management command (issue #1776).

Duplicate Differentia rows arise from untrimmed differentia_id values (e.g.
"101b" vs "101b "). The command merges each duplicate into its canonical row
and repoints affected chants.
"""

import io

from django.core.management import call_command
from django.test import TestCase

from main_app.models import Chant, Differentia
from main_app.tests.make_fakes import make_fake_chant

COMMAND = "merge_duplicate_differentiae"


class MergeDuplicateDifferentiaeTest(TestCase):

    def _run(self, **kwargs) -> str:
        out = io.StringIO()
        call_command(COMMAND, stdout=out, **kwargs)
        return out.getvalue()

    def test_trailing_whitespace_duplicate_is_merged(self) -> None:
        canonical = Differentia.objects.create(differentia_id="101b")
        duplicate = Differentia.objects.create(differentia_id="101b ")
        chant_on_canonical = make_fake_chant(diff_db=canonical)
        chant_on_duplicate = make_fake_chant(diff_db=duplicate)

        self._run()

        chant_on_canonical.refresh_from_db()
        chant_on_duplicate.refresh_from_db()
        self.assertEqual(chant_on_canonical.diff_db_id, canonical.pk)
        self.assertEqual(chant_on_duplicate.diff_db_id, canonical.pk)
        self.assertFalse(Differentia.objects.filter(pk=duplicate.pk).exists())
        self.assertTrue(Differentia.objects.filter(pk=canonical.pk).exists())

    def test_case_typo_t31A_is_merged_into_t31a(self) -> None:
        canonical = Differentia.objects.create(differentia_id="T31a")
        whitespace_dup = Differentia.objects.create(differentia_id="T31a ")
        case_dup = Differentia.objects.create(differentia_id="T31A")
        chant_case = make_fake_chant(diff_db=case_dup)
        chant_whitespace = make_fake_chant(diff_db=whitespace_dup)

        self._run()

        chant_case.refresh_from_db()
        chant_whitespace.refresh_from_db()
        self.assertEqual(chant_case.diff_db_id, canonical.pk)
        self.assertEqual(chant_whitespace.diff_db_id, canonical.pk)
        self.assertFalse(Differentia.objects.filter(pk=whitespace_dup.pk).exists())
        self.assertFalse(Differentia.objects.filter(pk=case_dup.pk).exists())
        self.assertTrue(Differentia.objects.filter(pk=canonical.pk).exists())

    def test_dry_run_writes_nothing(self) -> None:
        canonical = Differentia.objects.create(differentia_id="118a")
        duplicate = Differentia.objects.create(differentia_id="118a ")
        chant_on_duplicate = make_fake_chant(diff_db=duplicate)

        output = self._run(dry_run=True)

        chant_on_duplicate.refresh_from_db()
        self.assertEqual(chant_on_duplicate.diff_db_id, duplicate.pk)
        self.assertTrue(Differentia.objects.filter(pk=canonical.pk).exists())
        self.assertTrue(Differentia.objects.filter(pk=duplicate.pk).exists())
        self.assertIn("Dry run complete", output)
        self.assertIn("118a", output)

    def test_non_duplicate_differentiae_are_untouched(self) -> None:
        solo = Differentia.objects.create(differentia_id="19b")
        distinct = Differentia.objects.create(differentia_id="20c")

        output = self._run()

        self.assertTrue(Differentia.objects.filter(pk=solo.pk).exists())
        self.assertTrue(Differentia.objects.filter(pk=distinct.pk).exists())
        self.assertIn("No duplicate differentiae found", output)

    def test_multiple_duplicate_groups_are_all_merged(self) -> None:
        canonical_a = Differentia.objects.create(differentia_id="101b")
        duplicate_a = Differentia.objects.create(differentia_id="101b ")
        canonical_b = Differentia.objects.create(differentia_id="142a")
        duplicate_b = Differentia.objects.create(differentia_id="142a ")

        self._run()

        self.assertFalse(Differentia.objects.filter(pk=duplicate_a.pk).exists())
        self.assertFalse(Differentia.objects.filter(pk=duplicate_b.pk).exists())
        self.assertTrue(Differentia.objects.filter(pk=canonical_a.pk).exists())
        self.assertTrue(Differentia.objects.filter(pk=canonical_b.pk).exists())

    def test_canonical_with_no_chants_keeps_working(self) -> None:
        # The canonical row itself may have no chants pointing at it yet;
        # only the duplicate's chants need repointing.
        canonical = Differentia.objects.create(differentia_id="9c")
        duplicate = Differentia.objects.create(differentia_id="9c ")
        chant_on_duplicate = make_fake_chant(diff_db=duplicate)

        self._run()

        chant_on_duplicate.refresh_from_db()
        self.assertEqual(chant_on_duplicate.diff_db_id, canonical.pk)
        self.assertFalse(Differentia.objects.filter(pk=duplicate.pk).exists())
