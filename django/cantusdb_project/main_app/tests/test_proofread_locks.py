"""
Test that proofread fields are locked (#170, #2260): nobody can change a field
while its proofread box is ticked, and only proofreaders can untick it.
"""

from typing import Any, ClassVar

from django import forms
from django.test import SimpleTestCase, TestCase

from main_app.models import Chant, Source
from main_app.proofread_locks import (
    has_proofread_fields,
    lock_flag_for,
    lock_proofread_fields,
)

FLAGS = (
    "manuscript_full_text_std_proofread",
    "manuscript_full_text_proofread",
    "volpiano_proofread",
    "other_fields_proofread",
)


class LockFlagForTest(SimpleTestCase):
    def test_text_fields_lock_with_their_own_flag(self) -> None:
        expected = {
            "manuscript_full_text_std_spelling": "manuscript_full_text_std_proofread",
            "manuscript_full_text": "manuscript_full_text_proofread",
            "manuscript_syllabized_full_text": "manuscript_full_text_proofread",
            "volpiano": "volpiano_proofread",
            "chant_range": "volpiano_proofread",
        }
        for field, flag in expected.items():
            with self.subTest(field=field):
                self.assertEqual(lock_flag_for(field), flag)

    def test_other_fields_lock_with_other_fields_flag(self) -> None:
        for field in ("folio", "c_sequence", "cantus_id", "feast", "genre", "mode"):
            with self.subTest(field=field):
                self.assertEqual(lock_flag_for(field), "other_fields_proofread")

    def test_never_locked(self) -> None:
        for field in ("indexing_notes", "proofread_by", "source", "id", *FLAGS):
            with self.subTest(field=field):
                self.assertIsNone(lock_flag_for(field))


class HasProofreadFieldsTest(SimpleTestCase):
    def test_no_box_ticked(self) -> None:
        self.assertFalse(has_proofread_fields(Chant()))
        self.assertFalse(has_proofread_fields(Chant(volpiano_proofread=None)))

    def test_any_box_ticked(self) -> None:
        for flag in FLAGS:
            with self.subTest(flag=flag):
                self.assertTrue(has_proofread_fields(Chant(**{flag: True})))


class LockTestForm(forms.ModelForm):  # type: ignore[type-arg]
    class Meta:
        model = Chant
        fields = [
            "volpiano",
            "volpiano_proofread",
            "manuscript_full_text",
            "cantus_id",
            "other_fields_proofread",
            "indexing_notes",
        ]
        # as on the chant edit form
        widgets = {
            "volpiano_proofread": forms.CheckboxInput(),
            "other_fields_proofread": forms.CheckboxInput(),
        }


class LockProofreadFieldsTest(SimpleTestCase):
    def locked_fields(self, form: forms.ModelForm) -> set[str]:  # type: ignore[type-arg]
        return {name for name, field in form.fields.items() if field.disabled}

    def test_nothing_proofread(self) -> None:
        form = LockTestForm(instance=Chant())
        lock_proofread_fields(form)
        self.assertEqual(self.locked_fields(form), set())

    def test_each_box_locks_its_fields(self) -> None:
        form = LockTestForm(instance=Chant(volpiano_proofread=True))
        lock_proofread_fields(form)
        self.assertEqual(self.locked_fields(form), {"volpiano"})

        form = LockTestForm(instance=Chant(other_fields_proofread=True))
        lock_proofread_fields(form)
        # the indexing notes stay editable
        self.assertEqual(self.locked_fields(form), {"cantus_id"})

    def test_box_missing_from_form_still_locks(self) -> None:
        # the MS text box isn't on the form, but its field is
        form = LockTestForm(instance=Chant(manuscript_full_text_proofread=True))
        locks = lock_proofread_fields(form)
        self.assertEqual(self.locked_fields(form), {"manuscript_full_text"})
        self.assertNotIn("manuscript_full_text_proofread", locks)

    def test_returns_fields_each_box_on_the_form_locks(self) -> None:
        form = LockTestForm(instance=Chant())
        self.assertEqual(
            lock_proofread_fields(form),
            {
                "volpiano_proofread": ["volpiano"],
                "other_fields_proofread": ["cantus_id"],
            },
        )

    def test_null_flag_does_not_lock(self) -> None:
        form = LockTestForm(instance=Chant(volpiano_proofread=None))
        lock_proofread_fields(form)
        self.assertEqual(self.locked_fields(form), set())

    def test_proofreader_unlocks_a_field_by_submitting_it(self) -> None:
        # the page only submits a locked field once its box has been unticked
        chant = Chant(volpiano_proofread=True)
        for data in (
            {"volpiano": "1-a-3"},
            {"volpiano": "1-a-3", "volpiano_proofread": "on"},
        ):
            with self.subTest(data=data):
                form = LockTestForm(data=data, instance=chant)
                lock_proofread_fields(form, can_unlock=True)
                self.assertEqual(self.locked_fields(form), set())

    def test_field_left_out_stays_locked(self) -> None:
        chant = Chant(volpiano_proofread=True)
        for data in ({}, {"volpiano_proofread": "on"}):
            with self.subTest(data=data):
                form = LockTestForm(data=data, instance=chant)
                lock_proofread_fields(form, can_unlock=True)
                self.assertEqual(self.locked_fields(form), {"volpiano"})

        # an unbound form (the page as first shown) shows the saved lock
        form = LockTestForm(instance=chant)
        lock_proofread_fields(form, can_unlock=True)
        self.assertEqual(self.locked_fields(form), {"volpiano"})

    def test_others_cannot_unlock(self) -> None:
        chant = Chant(volpiano_proofread=True)
        form = LockTestForm(data={"volpiano": "1-a-3"}, instance=chant)
        lock_proofread_fields(form)
        self.assertEqual(self.locked_fields(form), {"volpiano"})

    def test_locked_field_is_not_required(self) -> None:
        # nobody can fill in a locked field, so leaving it empty can't be an error
        form = LockTestForm(instance=Chant(other_fields_proofread=True))
        form.fields["cantus_id"].required = True
        lock_proofread_fields(form)
        self.assertFalse(form.fields["cantus_id"].required)
