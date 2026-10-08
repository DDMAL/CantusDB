"""
Test that proofread fields are locked (#170, #2260): nobody can change a field
while its proofread box is ticked, and only proofreaders can untick it.
"""

from typing import Any, ClassVar

from django import forms
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from main_app.forms import ChantEditForm
from main_app.models import Chant, Source
from main_app.proofread_locks import (
    has_proofread_fields,
    lock_flag_for,
    lock_proofread_fields,
)
from main_app.tests.make_fakes import make_fake_chant, make_fake_source
from main_app.tests.mixins import CustomAccessTestMixin

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


class ProofreadLockTestCase(CustomAccessTestMixin, TestCase):
    source: ClassVar[Source]

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        # "user" is an indexer assigned to the source; "editor" is assigned to
        # it too, which makes them its proofreader
        cls.source = make_fake_source(
            published=True, current_editors=[cls.users["user"], cls.users["editor"]]
        )

    def make_chant(self, **flags: bool) -> Chant:
        return make_fake_chant(
            source=self.source,
            folio="001r",
            manuscript_full_text_std_spelling="ave maria gratia plena",
            manuscript_full_text="Ave maria gracia plena",
            volpiano="1---c---d---e---f---g---3",
            cantus_id="001234",
            indexing_notes="old notes",
            manuscript_syllabized_full_text=None,
            **flags,
        )

    def edit_data(self, chant: Chant, **changes: Any) -> dict[str, Any]:
        """The chant edit form as submitted with the chant's current values, plus `changes`."""
        data: dict[str, Any] = {
            "pk": chant.id,
            "source": self.source.id,
            "folio": chant.folio,
            "c_sequence": chant.c_sequence,
            "manuscript_full_text_std_spelling": chant.manuscript_full_text_std_spelling,
            "manuscript_full_text": chant.manuscript_full_text,
            "volpiano": chant.volpiano,
            "cantus_id": chant.cantus_id,
            "indexing_notes": chant.indexing_notes,
        }
        # a ticked checkbox is submitted, an unticked one is left out
        data.update({flag: "on" for flag in FLAGS if getattr(chant, flag)})
        for name, value in changes.items():
            if value is None:
                data.pop(name, None)
            else:
                data[name] = value
        return data

    def post_edit(self, user: str, chant: Chant, **changes: Any):
        self.client.force_login(self.users[user])
        return self.client.post(
            reverse("source-edit-chants", args=[self.source.id]),
            self.edit_data(chant, **changes),
        )


class ChantEditLockTest(ProofreadLockTestCase):
    def test_indexer_cannot_change_locked_fields(self) -> None:
        chant = self.make_chant(
            volpiano_proofread=True,
            manuscript_full_text_proofread=True,
            manuscript_full_text_std_proofread=True,
            other_fields_proofread=True,
        )
        response = self.post_edit(
            "user",
            chant,
            volpiano="1---a---3",
            manuscript_full_text="changed",
            manuscript_full_text_std_spelling="changed",
            cantus_id="999999",
            folio="002v",
            indexing_notes="new notes",
        )
        self.assertEqual(response.status_code, 302)
        chant.refresh_from_db()
        self.assertEqual(chant.volpiano, "1---c---d---e---f---g---3")
        self.assertEqual(chant.manuscript_full_text, "Ave maria gracia plena")
        self.assertEqual(
            chant.manuscript_full_text_std_spelling, "ave maria gratia plena"
        )
        self.assertEqual(chant.cantus_id, "001234")
        self.assertEqual(chant.folio, "001r")
        # the indexing notes are never locked
        self.assertEqual(chant.indexing_notes, "new notes")

    def test_indexer_can_change_unlocked_fields(self) -> None:
        chant = self.make_chant(volpiano_proofread=True)
        self.post_edit("user", chant, manuscript_full_text="changed", cantus_id="1")
        chant.refresh_from_db()
        self.assertEqual(chant.manuscript_full_text, "changed")
        self.assertEqual(chant.cantus_id, "1")
        # editing an unlocked field leaves the other boxes ticked
        self.assertIs(chant.volpiano_proofread, True)

    def test_indexer_cannot_tick_or_untick_boxes(self) -> None:
        chant = self.make_chant(volpiano_proofread=True)
        # a ticked box left out of the submission would untick it
        self.post_edit(
            "user", chant, volpiano_proofread=None, manuscript_full_text_proofread="on"
        )
        chant.refresh_from_db()
        self.assertIs(chant.volpiano_proofread, True)
        self.assertIs(chant.manuscript_full_text_proofread, False)

    def test_indexer_cannot_set_chant_range(self) -> None:
        chant = self.make_chant()
        self.post_edit("user", chant, chant_range="1---a---b---3")
        chant.refresh_from_db()
        self.assertNotEqual(chant.chant_range, "1---a---b---3")

    def test_indexer_keeps_proofread_by(self) -> None:
        chant = self.make_chant(volpiano_proofread=True)
        chant.proofread_by.set([self.users["editor"]])
        self.post_edit("user", chant, proofread_by=self.users["user"].id)
        self.assertEqual(list(chant.proofread_by.all()), [self.users["editor"]])

    def test_locked_text_left_out_of_submission_is_kept(self) -> None:
        # browsers don't submit disabled inputs; that must not blank the text
        chant = self.make_chant(
            manuscript_full_text_std_proofread=True,
            manuscript_full_text_proofread=True,
            volpiano_proofread=True,
        )
        response = self.post_edit(
            "user",
            chant,
            manuscript_full_text_std_spelling=None,
            manuscript_full_text=None,
            volpiano=None,
        )
        self.assertEqual(response.status_code, 302)
        chant.refresh_from_db()
        self.assertEqual(
            chant.manuscript_full_text_std_spelling, "ave maria gratia plena"
        )
        self.assertEqual(chant.manuscript_full_text, "Ave maria gracia plena")
        self.assertEqual(chant.volpiano, "1---c---d---e---f---g---3")

    def test_no_text_warnings_for_locked_text(self) -> None:
        # nobody can fix a locked text, so it isn't checked for problems
        chant = self.make_chant(manuscript_full_text_proofread=True)
        Chant.objects.filter(pk=chant.pk).update(manuscript_full_text="inv@lid")
        chant.refresh_from_db()
        form = ChantEditForm(self.edit_data(chant), instance=chant)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.text_problems, [])

    def test_proofreader_keeps_locked_field_left_out(self) -> None:
        # a field still locked on the page isn't submitted
        chant = self.make_chant(volpiano_proofread=True)
        self.post_edit("editor", chant, volpiano=None)
        chant.refresh_from_db()
        self.assertEqual(chant.volpiano, "1---c---d---e---f---g---3")
        self.assertIs(chant.volpiano_proofread, True)

    def test_proofreader_unticks_edits_and_reticks(self) -> None:
        # #170: untick to unlock, edit, tick again; all before saving
        chant = self.make_chant(volpiano_proofread=True)
        self.post_edit("editor", chant, volpiano="1---a---3")
        chant.refresh_from_db()
        self.assertEqual(chant.volpiano, "1---a---3")
        self.assertIs(chant.volpiano_proofread, True)

    def test_proofreader_unticks_and_edits_in_one_save(self) -> None:
        chant = self.make_chant(volpiano_proofread=True, other_fields_proofread=True)
        self.post_edit(
            "editor",
            chant,
            volpiano_proofread=None,
            volpiano="1---a---3",
            other_fields_proofread=None,
            cantus_id="999999",
        )
        chant.refresh_from_db()
        self.assertEqual(chant.volpiano, "1---a---3")
        self.assertIs(chant.volpiano_proofread, False)
        self.assertEqual(chant.cantus_id, "999999")
        self.assertIs(chant.other_fields_proofread, False)

    def test_proofreader_edits_and_ticks_in_one_save(self) -> None:
        chant = self.make_chant()
        self.post_edit("editor", chant, volpiano="1---a---3", volpiano_proofread="on")
        chant.refresh_from_db()
        self.assertEqual(chant.volpiano, "1---a---3")
        self.assertIs(chant.volpiano_proofread, True)

    def test_null_flag_does_not_lock(self) -> None:
        chant = self.make_chant()
        Chant.objects.filter(pk=chant.pk).update(volpiano_proofread=None)
        chant.refresh_from_db()
        self.post_edit("user", chant, volpiano="1---a---3")
        chant.refresh_from_db()
        self.assertEqual(chant.volpiano, "1---a---3")


class ChantEditPageTest(ProofreadLockTestCase):
    def get_edit_page(self, user: str, chant: Chant):
        self.client.force_login(self.users[user])
        return self.client.get(
            reverse("source-edit-chants", args=[self.source.id]), {"pk": chant.id}
        )

    def test_indexer_sees_proofread_status(self) -> None:
        # the boxes are shown read-only to indexers (#2175)
        chant = self.make_chant(volpiano_proofread=True)
        response = self.get_edit_page("user", chant)
        form = response.context["form"]
        for flag in FLAGS:
            with self.subTest(flag=flag):
                self.assertTrue(form.fields[flag].disabled)
                self.assertContains(response, f'name="{flag}"')
        self.assertTrue(form.fields["volpiano"].disabled)
        self.assertFalse(form.fields["manuscript_full_text"].disabled)
        self.assertContains(response, "Ask a proofreader")

    def test_proofreader_can_tick_boxes(self) -> None:
        chant = self.make_chant(volpiano_proofread=True)
        response = self.get_edit_page("editor", chant)
        form = response.context["form"]
        for flag in FLAGS:
            with self.subTest(flag=flag):
                self.assertFalse(form.fields[flag].disabled)
        self.assertTrue(form.fields["volpiano"].disabled)
        self.assertContains(response, "Untick the box to change them")
        # the page's script unlocks the fields when their box is unticked
        locks = response.context["proofread_locks"]
        self.assertIn("id_volpiano", locks["id_volpiano_proofread"])
        self.assertIn("id_chant_range", locks["id_volpiano_proofread"])
        self.assertIn("id_cantus_id", locks["id_other_fields_proofread"])
        self.assertNotIn("id_indexing_notes", locks["id_other_fields_proofread"])

    def test_no_lock_notice_without_proofread_fields(self) -> None:
        chant = self.make_chant()
        for user in ("user", "editor"):
            with self.subTest(user=user):
                response = self.get_edit_page(user, chant)
                self.assertNotContains(response, "are locked")
