"""Tests for the dedupe_indexing_notes management command (issue #2234)."""

import csv
import io
import os
import tempfile

from django.core.management import call_command
from django.test import TestCase
from reversion.models import Version

from main_app.management.commands.dedupe_indexing_notes import (
    collapse_repeated_note,
)
from main_app.models import Chant, Source
from main_app.tests.make_fakes import make_fake_chant, make_fake_source

COMMAND = "dedupe_indexing_notes"


class CollapseRepeatedNoteTest(TestCase):
    def test_one_note_repeated_becomes_one_note(self) -> None:
        self.assertEqual(collapse_repeated_note("ams186 | ams186 | ams186"), "ams186")

    def test_surrounding_spaces_are_ignored(self) -> None:
        self.assertEqual(collapse_repeated_note("ams186 | ams186 "), "ams186")

    def test_different_notes_are_left_alone(self) -> None:
        self.assertIsNone(collapse_repeated_note("ams186 | ams187"))

    def test_partial_duplicates_are_left_alone(self) -> None:
        self.assertIsNone(
            collapse_repeated_note('Foliation: "27... | Foliation: "27" in margin')
        )

    def test_notes_without_a_separator_are_left_alone(self) -> None:
        self.assertIsNone(collapse_repeated_note("ams186"))
        self.assertIsNone(collapse_repeated_note("a|a"))
        self.assertIsNone(collapse_repeated_note(""))
        self.assertIsNone(collapse_repeated_note(None))

    def test_blank_note_repeated_becomes_empty(self) -> None:
        self.assertEqual(collapse_repeated_note("\xa0 | \xa0 | \xa0"), "")

    def test_blank_part_next_to_a_note_is_left_alone(self) -> None:
        self.assertIsNone(collapse_repeated_note(' | "meum" is added above'))


class DedupeIndexingNotesCommandTest(TestCase):
    def setUp(self) -> None:
        self.source = make_fake_source()
        self.repeated = make_fake_chant(
            source=self.source, indexing_notes="ams186 | ams186 | ams186"
        )
        self.different = make_fake_chant(
            source=self.source, indexing_notes="ams186 | ams187"
        )

    def _run(self, *args: str) -> str:
        out = io.StringIO()
        call_command(COMMAND, *args, stdout=out)
        return out.getvalue()

    def test_repeated_note_is_collapsed(self) -> None:
        output = self._run()
        self.repeated.refresh_from_db()
        self.assertEqual(self.repeated.indexing_notes, "ams186")
        self.assertIn("Changed 1 chant(s) in 1 source(s).", output)

    def test_different_notes_are_not_changed(self) -> None:
        self._run()
        self.different.refresh_from_db()
        self.assertEqual(self.different.indexing_notes, "ams186 | ams187")

    def test_dry_run_writes_nothing(self) -> None:
        output = self._run("--dry-run")
        self.repeated.refresh_from_db()
        self.assertEqual(self.repeated.indexing_notes, "ams186 | ams186 | ams186")
        self.assertIn("Would change 1 chant(s) in 1 source(s).", output)

    def test_last_modified_dates_are_unchanged(self) -> None:
        chant_updated = Chant.objects.get(pk=self.repeated.pk).date_updated
        source_updated = Source.objects.get(pk=self.source.pk).date_updated
        self._run()
        self.assertEqual(
            Chant.objects.get(pk=self.repeated.pk).date_updated, chant_updated
        )
        self.assertEqual(
            Source.objects.get(pk=self.source.pk).date_updated, source_updated
        )

    def test_history_keeps_the_old_and_new_note(self) -> None:
        self._run()
        versions = (
            Version.objects.get_for_model(Chant)
            .filter(object_id=str(self.repeated.pk))
            .order_by("pk")
        )
        self.assertEqual(
            [version.field_dict["indexing_notes"] for version in versions],
            ["ams186 | ams186 | ams186", "ams186"],
        )

    def test_csv_lists_each_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "notes.csv")
            self._run("--dry-run", "--csv", path)
            with open(path, newline="", encoding="utf-8") as file:
                rows = list(csv.reader(file))
        self.assertEqual(
            rows,
            [
                ["chant_id", "source_id", "old_note", "new_note"],
                [
                    str(self.repeated.pk),
                    str(self.source.pk),
                    "ams186 | ams186 | ams186",
                    "ams186",
                ],
            ],
        )
