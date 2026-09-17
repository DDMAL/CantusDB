"""Tests for the merge_duplicate_differentiae management command (issue #1776).

Duplicate Differentia rows arise from untrimmed differentia_id values (e.g.
"101b" vs "101b "). The command merges each duplicate into its canonical row
and repoints affected chants.
"""

import io

from django.core.management import call_command
from django.test import TestCase
from reversion.models import Version

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


class MergeDuplicateDifferentiaeInformationTest(TestCase):
    """Merging must not discard mode/volpiano held by the row being deleted.

    #1776 asks for the entry "with more information (mode and volpiano)" to be
    kept, but the canonical row is chosen for its clean differentia_id, which
    is not necessarily the better-populated one.
    """

    def _run(self, **kwargs) -> str:
        out = io.StringIO()
        call_command(COMMAND, stdout=out, **kwargs)
        return out.getvalue()

    def test_duplicate_information_is_backfilled_onto_canonical(self) -> None:
        canonical = Differentia.objects.create(
            differentia_id="118a", mode=None, melodic_transcription=None
        )
        duplicate = Differentia.objects.create(
            differentia_id="118a ", mode="1", melodic_transcription="1--k-k-l-j"
        )
        make_fake_chant(diff_db=duplicate)

        self._run()

        canonical.refresh_from_db()
        self.assertEqual(canonical.mode, "1")
        self.assertEqual(canonical.melodic_transcription, "1--k-k-l-j")
        self.assertFalse(Differentia.objects.filter(pk=duplicate.pk).exists())

    def test_blank_duplicate_values_do_not_clear_canonical_values(self) -> None:
        canonical = Differentia.objects.create(
            differentia_id="101b", mode="2", melodic_transcription="1--k-j-h"
        )
        duplicate = Differentia.objects.create(
            differentia_id="101b ", mode="", melodic_transcription=None
        )
        make_fake_chant(diff_db=duplicate)

        self._run()

        canonical.refresh_from_db()
        self.assertEqual(canonical.mode, "2")
        self.assertEqual(canonical.melodic_transcription, "1--k-j-h")

    def test_conflicting_duplicate_values_are_reported_not_applied(self) -> None:
        canonical = Differentia.objects.create(differentia_id="9c", mode="2")
        duplicate = Differentia.objects.create(differentia_id="9c ", mode="7")
        make_fake_chant(diff_db=duplicate)

        output = self._run()

        canonical.refresh_from_db()
        self.assertEqual(canonical.mode, "2")
        self.assertIn("Conflict", output)
        self.assertIn("mode", output)

    def test_dry_run_reports_planned_backfill_without_writing(self) -> None:
        canonical = Differentia.objects.create(differentia_id="19b", mode=None)
        duplicate = Differentia.objects.create(differentia_id="19b ", mode="3")
        make_fake_chant(diff_db=duplicate)

        output = self._run(dry_run=True)

        canonical.refresh_from_db()
        self.assertIsNone(canonical.mode)
        self.assertIn("Backfill", output)
        self.assertIn("mode", output)


class MergeDuplicateDifferentiaeRevisionTest(TestCase):
    """The merge deletes rows and rewrites FKs, so it must stay recoverable.

    django-reversion drops versions of rows that no longer exist when the
    revision closes, and its post_save handler overwrites an earlier snapshot
    with the post-save state, so recording the pre-merge state needs a revision
    that closes before the merge runs. These tests pin that down.
    """

    def _run(self, **kwargs) -> str:
        out = io.StringIO()
        call_command(COMMAND, stdout=out, **kwargs)
        return out.getvalue()

    def test_deleted_duplicate_is_recorded_before_deletion(self) -> None:
        Differentia.objects.create(differentia_id="101b")
        duplicate = Differentia.objects.create(
            differentia_id="101b ", mode="2", melodic_transcription="1--k-j-h"
        )
        make_fake_chant(diff_db=duplicate)
        duplicate_pk = duplicate.pk

        self._run()

        self.assertFalse(Differentia.objects.filter(pk=duplicate_pk).exists())
        versions = Version.objects.get_for_model(Differentia).filter(
            object_id=str(duplicate_pk)
        )
        self.assertEqual(versions.count(), 1)
        recorded = versions.first().field_dict
        self.assertEqual(recorded["differentia_id"], "101b ")
        self.assertEqual(recorded["mode"], "2")
        self.assertEqual(recorded["melodic_transcription"], "1--k-j-h")

    def test_repointed_chant_records_old_and_new_link(self) -> None:
        canonical = Differentia.objects.create(differentia_id="9c")
        duplicate = Differentia.objects.create(differentia_id="9c ")
        chant = make_fake_chant(diff_db=duplicate)
        duplicate_pk = duplicate.pk

        self._run()

        versions = (
            Version.objects.get_for_model(Chant)
            .filter(object_id=str(chant.pk))
            .order_by("pk")
        )
        self.assertEqual(
            [version.field_dict["diff_db_id"] for version in versions],
            [duplicate_pk, canonical.pk],
        )

    def test_merge_can_be_fully_undone_from_its_revisions(self) -> None:
        canonical = Differentia.objects.create(differentia_id="142a")
        duplicate = Differentia.objects.create(
            differentia_id="142a ", mode="4", melodic_transcription="1--h-g-h"
        )
        chant = make_fake_chant(diff_db=duplicate)
        duplicate_pk = duplicate.pk

        self._run()

        chant.refresh_from_db()
        self.assertEqual(chant.diff_db_id, canonical.pk)

        # Restore the deleted row before the chant that points back at it.
        Version.objects.get_for_model(Differentia).get(
            object_id=str(duplicate_pk)
        ).revert()
        restored = Differentia.objects.get(pk=duplicate_pk)
        self.assertEqual(restored.differentia_id, "142a ")
        self.assertEqual(restored.mode, "4")

        Version.objects.get_for_model(Chant).filter(object_id=str(chant.pk)).order_by(
            "pk"
        ).first().revert()
        chant.refresh_from_db()
        self.assertEqual(chant.diff_db_id, duplicate_pk)
