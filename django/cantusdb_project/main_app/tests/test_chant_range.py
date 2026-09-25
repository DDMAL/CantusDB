"""Range persistence and form transitions for chants and sequences."""

from io import StringIO

import reversion
from reversion.models import Version
from django.core.management import call_command
from django.test import TestCase

from main_app.forms import ChantEditForm
from main_app.tests.make_fakes import make_fake_chant, make_fake_sequence


class ChantRangePersistenceTest(TestCase):
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
        chant.chant_range = "1-a-b-4"
        chant.save(update_fields=["chant_range"])
        chant.refresh_from_db()
        self.assertEqual(chant.volpiano, "1---c--g---4")
        self.assertEqual(chant.chant_range, "1-c-g-4")

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
                    response, "Clear Volpiano to enter a range by hand."
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
                form = form_class(data=data, instance=record)
                self.assertFalse(form.is_valid())
                self.assertIn("chant_range", form.errors)
