"""Range persistence and form transitions for chants and sequences."""

from io import StringIO
import json
from contextlib import nullcontext
from unittest.mock import patch

import reversion
from reversion.models import Version
from django.core.management import call_command
from django.db import connection, transaction
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.forms.models import model_to_dict

from main_app.forms import ChantEditForm, AdminChantForm, AdminSequenceForm
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_sequence,
    make_fake_user,
)


class ChantRangePersistenceTest(TestCase):
    def test_command_with_active_revision_keeps_original_range(self) -> None:
        chant = make_fake_chant(volpiano="1---c--g---4", cantus_id="old-id")
        type(chant).objects.filter(pk=chant.pk).update(chant_range="1-a-b-4")
        call_command("map_cantus_ids", "old-id", "new-id", stdout=StringIO())
        versions = Version.objects.get_for_object(chant)
        self.assertEqual(
            [
                (v.field_dict["cantus_id"], v.field_dict["chant_range"])
                for v in versions
            ],
            [("new-id", "1-a-b-4")],
        )
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")

    def test_outer_revision_failure_rolls_back_baseline_and_range(self) -> None:
        chant = make_fake_chant(volpiano="1---c--g---4")
        type(chant).objects.filter(pk=chant.pk).update(chant_range="1-a-b-4")
        chant.refresh_from_db()
        chant.volpiano = "2---c--g---4"
        with self.assertRaises(RuntimeError):
            with reversion.create_revision():
                chant.save()
                raise RuntimeError("The rest of the request failed")
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")
        self.assertFalse(Version.objects.get_for_object(chant).exists())

    def test_active_revision_preserves_legacy_range_before_melody_edit(self) -> None:
        for factory in (make_fake_chant, make_fake_sequence):
            with self.subTest(model=factory.__name__):
                record = factory()
                type(record).objects.filter(pk=record.pk).update(
                    volpiano="1---c--g---4", chant_range="1-a-b-4"
                )
                record.refresh_from_db()
                self.assertFalse(Version.objects.get_for_object(record).exists())
                with reversion.create_revision():
                    record.volpiano = "2---c--g---4"
                    record.indexing_notes = "An unrelated edit"
                    record.save()
                    reversion.set_comment("Updated indexing notes")
                versions = Version.objects.get_for_object(record)
                self.assertEqual(
                    [v.field_dict["chant_range"] for v in versions],
                    ["2-c-g-4", "1-a-b-4"],
                )
                self.assertEqual(
                    versions.first().revision.comment, "Updated indexing notes"
                )
                versions.last().revision.revert()
                record.refresh_from_db()
                self.assertEqual(record.chant_range, "1-a-b-4")

    def test_clearing_melody_without_javascript_preserves_range(self) -> None:
        for factory, form_class in (
            (make_fake_chant, ChantEditForm),
            (make_fake_chant, AdminChantForm),
            (make_fake_sequence, AdminSequenceForm),
        ):
            with self.subTest(form=form_class):
                record = factory()
                type(record).objects.filter(pk=record.pk).update(
                    volpiano="1---c--g---4", chant_range="1-c-g-4"
                )
                record.refresh_from_db()
                self.assertTrue(
                    form_class(instance=record).fields["chant_range"].disabled
                )
                data = model_to_dict(record)
                data["volpiano"] = ""
                data.pop("chant_range")
                form = form_class(instance=record, data=data)
                self.assertTrue(form.is_valid(), form.errors)
                self.assertNotIn("chant_range", form.changed_data)
                form.save()
                record.refresh_from_db()
                self.assertEqual(record.volpiano, "")
                self.assertEqual(record.chant_range, "1-c-g-4")
                self.assertFalse(
                    form_class(instance=record).fields["chant_range"].disabled
                )

    def test_adding_underivable_melody_preserves_manual_range(self) -> None:
        for factory, form_class in (
            (make_fake_chant, ChantEditForm),
            (make_fake_chant, AdminChantForm),
            (make_fake_sequence, AdminSequenceForm),
        ):
            for melody in ("1---c--2---d---4", "1---3---4"):
                for omitted in (True, False):
                    with self.subTest(form=form_class, melody=melody, omitted=omitted):
                        record = factory()
                        type(record).objects.filter(pk=record.pk).update(
                            volpiano="", chant_range="1-c-d-4"
                        )
                        record.refresh_from_db()
                        data = model_to_dict(record)
                        data["volpiano"] = melody
                        if omitted:
                            # Preserve omitted inputs as well as unchanged ones.
                            data.pop("chant_range")
                        form = form_class(instance=record, data=data)
                        self.assertTrue(form.is_valid(), form.errors)
                        self.assertNotIn("chant_range", form.changed_data)
                        form.save()
                        record.refresh_from_db()
                        self.assertEqual(record.volpiano, melody)
                        self.assertEqual(record.chant_range, "1-c-d-4")

    def test_underivable_melodies_allow_manual_range_edits(self) -> None:
        for factory, form_class in (
            (make_fake_chant, ChantEditForm),
            (make_fake_chant, AdminChantForm),
            (make_fake_sequence, AdminSequenceForm),
        ):
            for melody in ("1---c--2---d---4", "1---3---4"):
                for initial_melody in ("", melody, "1---c--g---4"):
                    with self.subTest(
                        form=form_class, melody=melody, initial=initial_melody
                    ):
                        record = factory()
                        type(record).objects.filter(pk=record.pk).update(
                            volpiano=initial_melody, chant_range="1-c-g-4"
                        )
                        record.refresh_from_db()
                        if initial_melody == melody:
                            self.assertFalse(
                                form_class(instance=record)
                                .fields["chant_range"]
                                .disabled
                            )
                        data = model_to_dict(record)
                        data.update(volpiano=melody, chant_range="1-d-h-4")
                        form = form_class(instance=record, data=data)
                        self.assertFalse(form.fields["chant_range"].disabled)
                        self.assertTrue(form.is_valid(), form.errors)
                        self.assertIn("chant_range", form.changed_data)
                        form.save()
                        record.refresh_from_db()
                        self.assertEqual(record.volpiano, melody)
                        self.assertEqual(record.chant_range, "1-d-h-4")

    def test_filling_blank_ranges_records_before_and_after(self) -> None:
        for factory in (make_fake_chant, make_fake_sequence):
            with self.subTest(model=factory.__name__):
                record = factory()
                type(record).objects.filter(pk=record.pk).update(
                    volpiano="1---c--g---4", chant_range=""
                )
                record.refresh_from_db()
                record.save()
                versions = Version.objects.get_for_object(record)
                self.assertEqual(
                    [v.field_dict["chant_range"] for v in versions],
                    ["1-c-g-4", ""],
                )
                versions.last().revision.revert()
                record.refresh_from_db()
                self.assertEqual(record.chant_range, "")

    def test_touch_all_chants_preserves_legacy_disagreements(self) -> None:
        chant = make_fake_chant(volpiano="1---c--g---4")
        type(chant).objects.filter(pk=chant.pk).update(chant_range="1-a-b-4")
        call_command("touch_all_chants", stdout=StringIO())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")
        self.assertFalse(Version.objects.get_for_object(chant).exists())

    def test_failed_maintenance_save_rolls_back_range_and_revisions(self) -> None:
        chant = make_fake_chant(volpiano="1---c--g---4")
        type(chant).objects.filter(pk=chant.pk).update(chant_range="1-a-b-4")
        chant.refresh_from_db()
        chant.volpiano = "2---c--g---4"
        original_add = reversion.add_to_revision

        def fail_after_write(record, **kwargs):
            if record.chant_range == "2-c-g-4":
                raise RuntimeError("revision write failed")
            original_add(record, **kwargs)

        with patch("reversion.add_to_revision", side_effect=fail_after_write):
            with self.assertRaises(RuntimeError):
                chant.save()
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")
        self.assertFalse(Version.objects.get_for_object(chant).exists())

    def test_ordinary_saves_preserve_nonblank_legacy_ranges(self) -> None:
        for factory in (make_fake_chant, make_fake_sequence):
            for update_fields in (None, ["volpiano"], ["chant_range"]):
                with self.subTest(model=factory.__name__, fields=update_fields):
                    record = factory()
                    type(record).objects.filter(pk=record.pk).update(
                        volpiano="1---c--g---4", chant_range="1-a-b-4"
                    )
                    record.refresh_from_db()
                    record.indexing_notes = "Unrelated edit"
                    record.save(update_fields=update_fields)
                    record.refresh_from_db()
                    self.assertEqual(record.chant_range, "1-a-b-4")
                    self.assertFalse(Version.objects.get_for_object(record).exists())

    def test_form_whitespace_normalization_preserves_legacy_range(self):
        for factory, form_class in (
            (make_fake_chant, ChantEditForm),
            (make_fake_chant, AdminChantForm),
            (make_fake_sequence, AdminSequenceForm),
        ):
            for melody in (
                " 1---c--g---4",
                "1---c--g---4 \t",
                "1---c--\ng---4",
                "1---c--\rg---4",
            ):
                with self.subTest(form=form_class, melody=repr(melody)):
                    record = factory()
                    type(record).objects.filter(pk=record.pk).update(
                        volpiano=melody, chant_range="1-a-b-4"
                    )
                    record.refresh_from_db()
                    data = model_to_dict(record)
                    data["volpiano"] = melody.replace("\r", "\n").replace("\n", "\r\n")
                    data["indexing_notes"] = "An unrelated edit"
                    form = form_class(instance=record, data=data)
                    self.assertTrue(form.is_valid(), form.errors)
                    form.save()
                    record.refresh_from_db()
                    self.assertEqual(record.chant_range, "1-a-b-4")
                    self.assertEqual(record.indexing_notes, "An unrelated edit")
                    self.assertFalse(Version.objects.get_for_object(record).exists())

    def test_retry_after_rollback_retains_original_range_history(self):
        for factory in (make_fake_chant, make_fake_sequence):
            for active_revision in (False, True):
                with self.subTest(
                    model=factory.__name__, active_revision=active_revision
                ):
                    record = factory()
                    type(record).objects.filter(pk=record.pk).update(
                        volpiano="1---c--g---4", chant_range="1-a-b-4"
                    )
                    record.refresh_from_db()
                    record.volpiano = "2---c--g---4"
                    with self.assertRaises(RuntimeError):
                        with transaction.atomic():
                            with (
                                reversion.create_revision()
                                if active_revision
                                else nullcontext()
                            ):
                                record.save()
                            raise RuntimeError("Later work failed")
                    self.assertFalse(Version.objects.get_for_object(record).exists())
                    # Retry the same object, whose field values were not rolled back.
                    record.save()
                    record.refresh_from_db()
                    self.assertEqual(record.chant_range, "2-c-g-4")
                    self.assertEqual(
                        [
                            v.field_dict["chant_range"]
                            for v in Version.objects.get_for_object(record)
                        ],
                        ["2-c-g-4", "1-a-b-4"],
                    )

    def test_underivable_to_derivable_rejects_new_manual_range(self):
        for factory, form_class in (
            (make_fake_chant, ChantEditForm),
            (make_fake_chant, AdminChantForm),
            (make_fake_sequence, AdminSequenceForm),
        ):
            for melody in ("1---c--2---d---4", "1---3---4"):
                for prefix in (None, "review"):
                    with self.subTest(form=form_class, melody=melody, prefix=prefix):
                        record = factory()
                        type(record).objects.filter(pk=record.pk).update(
                            volpiano=melody, chant_range="1-e-f-4"
                        )
                        record.refresh_from_db()
                        self.assertFalse(
                            form_class(instance=record).fields["chant_range"].disabled
                        )
                        data = model_to_dict(record)
                        data.update(volpiano="1---c--g---4", chant_range="1-d-h-4")
                        if prefix:
                            data = {
                                f"{prefix}-{key}": value for key, value in data.items()
                            }
                        form = form_class(instance=record, data=data, prefix=prefix)
                        self.assertFalse(form.is_valid())
                        self.assertIn("chant_range", form.errors)
                        self.assertEqual(form["chant_range"].value(), "1-d-h-4")
                        record.refresh_from_db()
                        self.assertEqual(record.volpiano, melody)
                        self.assertEqual(record.chant_range, "1-e-f-4")

    def test_underivable_to_derivable_accepts_preserved_or_empty_range(self):
        for factory, form_class in (
            (make_fake_chant, ChantEditForm),
            (make_fake_chant, AdminChantForm),
            (make_fake_sequence, AdminSequenceForm),
        ):
            for submitted_range in (None, "", "1-e-f-4"):
                with self.subTest(form=form_class, submitted_range=submitted_range):
                    record = factory()
                    type(record).objects.filter(pk=record.pk).update(
                        volpiano="1---c--2---d---4", chant_range="1-e-f-4"
                    )
                    record.refresh_from_db()
                    data = model_to_dict(record)
                    data["volpiano"] = "1---c--g---4"
                    if submitted_range is None:
                        data.pop("chant_range")
                    else:
                        data["chant_range"] = submitted_range
                    form = form_class(instance=record, data=data)
                    self.assertTrue(form.is_valid(), form.errors)
                    form.save()
                    record.refresh_from_db()
                    self.assertEqual(record.chant_range, "1-c-g-4")

    def test_matching_ranges_skip_locked_reads_and_extra_range_reads(self) -> None:
        for factory in (make_fake_chant, make_fake_sequence):
            with self.captureOnCommitCallbacks(execute=True):
                record = factory()
                record.volpiano = "1---c--g---4"
                record.save()
            for record in (record, type(record).objects.get(pk=record.pk)):
                with self.subTest(model=factory.__name__):
                    with CaptureQueriesContext(connection) as queries:
                        record.indexing_notes = "Unrelated edit"
                        record.save()
                    self.assertFalse(
                        any("FOR UPDATE" in query["sql"] for query in queries)
                    )
                    self.assertFalse(
                        any(
                            query["sql"].startswith("SELECT")
                            and '"chant_range"' in query["sql"]
                            and record._meta.db_table in query["sql"]
                            for query in queries
                        )
                    )

    def test_preassigned_derived_range_still_keeps_baseline_on_melody_change(self):
        record = make_fake_chant(volpiano="1---c--g---4")
        record.volpiano = "2---d--h---4"
        record.chant_range = "2-d-h-4"
        record.save()
        self.assertEqual(
            [
                v.field_dict["chant_range"]
                for v in Version.objects.get_for_object(record)
            ],
            ["2-d-h-4", "1-c-g-4"],
        )

    def test_refreshed_legacy_range_is_audited_when_melody_changes(self):
        record = make_fake_chant(volpiano="1---c--g---4")
        type(record).objects.filter(pk=record.pk).update(chant_range="1-a-b-4")
        record.refresh_from_db(fields=["chant_range"])
        record.volpiano = "1---c--e--g---4"
        record.chant_range = "1-c-g-4"
        record.save()
        self.assertEqual(
            [
                v.field_dict["chant_range"]
                for v in Version.objects.get_for_object(record)
            ],
            ["1-c-g-4", "1-a-b-4"],
        )

    def test_blank_range_is_filled_even_when_melody_is_unchanged(self):
        for blank in (None, "", " \t"):
            for update_fields in (None, ["volpiano"], ["chant_range"]):
                with self.subTest(blank=blank, fields=update_fields):
                    record = make_fake_chant(volpiano="1---c--g---4")
                    type(record).objects.filter(pk=record.pk).update(chant_range=blank)
                    record.refresh_from_db()
                    record.save(update_fields=update_fields)
                    record.refresh_from_db()
                    self.assertEqual(record.chant_range, "1-c-g-4")

    def test_deferred_melody_edit_derives_range_and_preserves_baseline(self):
        for factory in (make_fake_chant, make_fake_sequence):
            record = factory()
            type(record).objects.filter(pk=record.pk).update(
                volpiano="1---c--g---4", chant_range="1-a-b-4"
            )
            record = type(record).objects.only("pk").get(pk=record.pk)
            record.volpiano = "2---d--h---4"
            record.save(update_fields=["volpiano"])
            record.refresh_from_db()
            self.assertEqual(record.chant_range, "2-d-h-4")
            self.assertEqual(
                [
                    v.field_dict["chant_range"]
                    for v in Version.objects.get_for_object(record)
                ],
                ["2-d-h-4", "1-a-b-4"],
            )

    def test_unchanged_and_unrelated_partial_saves_do_not_create_revisions(
        self,
    ) -> None:
        chant = make_fake_chant(volpiano="1---c--g---4")
        chant.save()
        self.assertFalse(Version.objects.get_for_object(chant).exists())
        type(chant).objects.filter(pk=chant.pk).update(chant_range="1-a-b-4")
        chant.refresh_from_db()
        chant.indexing_notes = "Updated notes"
        chant.save(update_fields=["indexing_notes"])
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")
        self.assertFalse(Version.objects.get_for_object(chant).exists())

    def test_revision_and_instance_hold_the_derived_range(self) -> None:
        for factory in (make_fake_chant, make_fake_sequence):
            with self.subTest(model=factory.__name__):
                record = factory()
                record.volpiano = "2---c--g---4"
                record.chant_range = "1-a-b-4"
                with reversion.create_revision():
                    record.save()
                self.assertEqual(record.chant_range, "2-c-g-4")
                version = Version.objects.get_for_object(record).first()
                self.assertEqual(version.field_dict["chant_range"], "2-c-g-4")
                record.refresh_from_db()
                self.assertEqual(record.chant_range, "2-c-g-4")

    def test_partial_melody_save_updates_range_and_revision(self) -> None:
        for factory in (make_fake_chant, make_fake_sequence):
            with self.subTest(model=factory.__name__):
                record = factory()
                record.volpiano = "1---d--h---4"
                with reversion.create_revision():
                    record.save(update_fields=["volpiano"])
                self.assertEqual(record.chant_range, "1-d-h-4")
                self.assertEqual(
                    Version.objects.get_for_object(record)
                    .first()
                    .field_dict["chant_range"],
                    "1-d-h-4",
                )
                record.refresh_from_db()
                self.assertEqual(record.chant_range, "1-d-h-4")

    def test_stale_partial_melody_save_rechecks_persisted_range(self) -> None:
        """Partial saves reconcile newer melodies/blank ranges but keep legacy ranges."""
        for factory in (make_fake_chant, make_fake_sequence):
            for melody, stored_range, expected_range in (
                ("2---d--h---4", "2-d-h-4", "1-c-g-4"),
                ("1---c--g---4", "", "1-c-g-4"),
                ("1---c--g---4", "1-a-b-4", "1-a-b-4"),
            ):
                with self.subTest(model=factory.__name__, stored_range=stored_range):
                    record = factory()
                    records = type(record).objects
                    records.filter(pk=record.pk).update(
                        volpiano="1---c--g---4", chant_range="1-c-g-4"
                    )
                    stale = records.get(pk=record.pk)
                    # Another writer changes the row after this instance was loaded.
                    records.filter(pk=record.pk).update(
                        volpiano=melody,
                        chant_range=stored_range,
                        indexing_notes="Another editor's notes",
                    )
                    stale.indexing_notes = "An unsaved edit"
                    stale.save(update_fields=["volpiano"])
                    record.refresh_from_db()
                    self.assertEqual(record.volpiano, "1---c--g---4")
                    self.assertEqual(record.chant_range, expected_range)
                    self.assertEqual(record.indexing_notes, "Another editor's notes")
                    self.assertEqual(
                        [
                            v.field_dict["chant_range"]
                            for v in Version.objects.get_for_object(record)
                        ],
                        (
                            [expected_range, stored_range]
                            if expected_range != stored_range
                            else []
                        ),
                    )

    def test_backfill_records_old_and_new_ranges(self) -> None:
        for factory in (make_fake_chant, make_fake_sequence):
            with self.subTest(model=factory.__name__):
                record = factory()
                type(record).objects.filter(pk=record.pk).update(
                    volpiano="1---c--g---4", chant_range="1-a-b-4"
                )
                call_command("populate_chant_ranges", "--overwrite", stdout=StringIO())
                versions = Version.objects.get_for_object(record)
                self.assertEqual(
                    [v.field_dict["chant_range"] for v in versions],
                    ["1-c-g-4", "1-a-b-4"],
                )
                self.assertTrue(
                    all("populate_chant_ranges" in v.revision.comment for v in versions)
                )
                versions.last().revision.revert()
                record.refresh_from_db()
                self.assertEqual(record.chant_range, "1-a-b-4")

    def test_clearing_melody_allows_manual_range_in_same_form(self) -> None:
        chant = make_fake_chant(volpiano="1---c--g---4")
        form = ChantEditForm(
            instance=chant,
            data={
                "source": chant.source_id,
                "folio": chant.folio,
                "c_sequence": chant.c_sequence,
                "manuscript_full_text_std_spelling": "Lorem ipsum",
                "volpiano": "",
                "chant_range": "1-e-h-4",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-e-h-4")

    def test_partial_range_save_uses_the_persisted_melody(self) -> None:
        chant = make_fake_chant(volpiano="1---c--g---4")
        chant.volpiano = "2---d--h---4"
        chant.chant_range = ""
        chant.save(update_fields=["chant_range"])
        chant.refresh_from_db()
        self.assertEqual(chant.volpiano, "1---c--g---4")
        self.assertEqual(chant.chant_range, "1-c-g-4")

    def test_partial_melody_save_does_not_use_unsaved_blank_range(self):
        chant = make_fake_chant(volpiano="1---c--g---4")
        type(chant).objects.filter(pk=chant.pk).update(chant_range="1-a-b-4")
        chant.refresh_from_db()
        chant.chant_range = ""
        chant.save(update_fields=["volpiano"])
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")

    def test_baseline_serialization_matches_reversion(self):
        from main_app.range_revisions import record_range_baseline

        user = make_fake_user()
        for factory in (make_fake_chant, make_fake_sequence):
            with self.subTest(model=factory.__name__):
                record = factory()
                record.proofread_by.add(user)
                record.refresh_from_db()
                with reversion.create_revision(manage_manually=True):
                    reversion.set_user(user)
                    record_range_baseline(record, "default")
                    baseline = Version.objects.get_for_object(record).get()
                    reversion.add_to_revision(record)
                standard = Version.objects.get_for_object(record).first()
                self.assertNotEqual(baseline.pk, standard.pk)
                self.assertEqual(standard.revision.version_set.count(), 1)
                self.assertEqual(
                    json.loads(baseline.serialized_data),
                    json.loads(standard.serialized_data),
                )
                for field in (
                    "content_type_id",
                    "object_id",
                    "object_repr",
                    "format",
                    "db",
                ):
                    self.assertEqual(getattr(baseline, field), getattr(standard, field))
                self.assertEqual(baseline.field_dict, standard.field_dict)
                self.assertEqual(baseline.revision.user, standard.revision.user)

    def test_dry_run_and_matching_ranges_create_no_revisions(self) -> None:
        chant = make_fake_chant(volpiano="1---c--g---4")
        call_command("populate_chant_ranges", "--overwrite", stdout=StringIO())
        self.assertFalse(Version.objects.get_for_object(chant).exists())
        type(chant).objects.filter(pk=chant.pk).update(chant_range="1-a-b-4")
        call_command(
            "populate_chant_ranges", "--overwrite", "--dry-run", stdout=StringIO()
        )
        self.assertFalse(Version.objects.get_for_object(chant).exists())
        chant.refresh_from_db()
        self.assertEqual(chant.chant_range, "1-a-b-4")

    def test_backfill_rechecks_melody_and_manual_range_after_scanning(self) -> None:
        from unittest.mock import patch

        from main_app.chant_range import generate_chant_range
        from main_app.management.commands.populate_chant_ranges import Command

        for changes, overwrite, expected in (
            ({"volpiano": "2---d--h---4"}, True, "2-d-h-4"),
            ({"chant_range": "1-e-f-4"}, False, "1-e-f-4"),
        ):
            with self.subTest(changes=changes):
                chant = make_fake_chant(volpiano="1---c--g---4")
                type(chant).objects.filter(pk=chant.pk).update(chant_range="")
                changed = False

                def edit_after_scan(volpiano: str) -> str:
                    nonlocal changed
                    if not changed:
                        changed = True
                        type(chant).objects.filter(pk=chant.pk).update(**changes)
                    return generate_chant_range(volpiano)

                with patch(
                    "main_app.management.commands.populate_chant_ranges.generate_chant_range",
                    side_effect=edit_after_scan,
                ):
                    count = Command().backfill(
                        type(chant), dry_run=False, overwrite=overwrite
                    )
                chant.refresh_from_db()
                self.assertEqual(chant.chant_range, expected)
                self.assertEqual(count, int(overwrite))


class AdminChantRangeTest(TestCase):
    def test_admin_uses_the_range_rule_and_includes_its_script(self) -> None:
        from django.contrib.auth import get_user_model
        from django.urls import reverse

        self.client.force_login(
            get_user_model().objects.create_superuser(
                email="range-admin@example.invalid", password="test-password"
            )
        )
        for factory in (make_fake_chant, make_fake_sequence):
            with self.subTest(model=factory.__name__):
                record = factory()
                record.volpiano = "1---c--g---4"
                record.save()
                response = self.client.get(
                    reverse(
                        f"admin:main_app_{record._meta.model_name}_change",
                        args=[record.pk],
                    )
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(
                    response.context["adminform"].form.fields["chant_range"].disabled
                )
                self.assertContains(response, 'src="/static/js/chant_range.js"')
                self.assertContains(
                    response,
                    "Enter a range by hand if Volpiano is blank or its range cannot be calculated.",
                )

    def test_admin_cannot_override_melody_but_can_clear_it_for_manual_entry(
        self,
    ) -> None:
        from django.forms.models import model_to_dict
        from main_app.forms import AdminChantForm, AdminSequenceForm

        for factory, form_class in (
            (make_fake_chant, AdminChantForm),
            (make_fake_sequence, AdminSequenceForm),
        ):
            with self.subTest(model=factory.__name__):
                record = factory()
                record.volpiano = "2---c--g---4"
                record.save()
                data = model_to_dict(record)
                data["chant_range"] = "1-a-b-4"
                form = form_class(data=data, instance=record)
                self.assertTrue(form.is_valid(), form.errors)
                form.save()
                record.refresh_from_db()
                self.assertEqual(record.chant_range, "2-c-g-4")
                data["volpiano"] = ""
                form = form_class(data=data, instance=record)
                self.assertTrue(form.is_valid(), form.errors)
                form.save()
                record.refresh_from_db()
                self.assertEqual(record.chant_range, "1-a-b-4")
                data["volpiano"] = "1---c--g---4"
                # An unchanged range is allowed when adding a melody without
                # JavaScript, but a new manual override is still rejected.
                data["chant_range"] = "1-d-h-4"
                form = form_class(data=data, instance=record)
                self.assertFalse(form.is_valid())
                self.assertIn("chant_range", form.errors)
