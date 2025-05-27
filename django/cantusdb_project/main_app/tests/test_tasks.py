from typing import List, Dict, Any

from django.test import TestCase
from django.db.models import QuerySet

from main_app.tasks import save_browse_chants_formset
from main_app.tests.make_fakes import make_fake_source, make_fake_chant
from main_app.models import Chant, Source
from main_app.forms import BrowseChantsBulkEditFormset


class SaveBrowseChantsFormsetTest(TestCase):
    source: Source
    chants: List[Chant]
    initial_form_data: Dict[str, Any]
    chant_ids: List[int]

    @classmethod
    def setUpTestData(cls) -> None:
        cls.source = make_fake_source()
        cls.chants = [
            make_fake_chant(source=cls.source),
            make_fake_chant(source=cls.source),
        ]
        queryset = Chant.objects.filter(source=cls.source)
        formset = BrowseChantsBulkEditFormset(
            queryset=queryset,
        )
        cls.chant_ids = list(queryset.values_list("id", flat=True))
        # Collect the initial formset data
        management_form_data = {
            f"chant_set-{key}": str(value)
            for key, value in formset.management_form.initial.items()
        }
        chant_1_form_data = {
            f"chant_set-0-{key}": value
            for key, value in formset.forms[0].initial.items()
        }
        chant_2_form_data = {
            f"chant_set-1-{key}": value
            for key, value in formset.forms[1].initial.items()
        }
        complete_form_data = management_form_data.copy()
        complete_form_data.update(chant_1_form_data)
        complete_form_data.update(chant_2_form_data)
        cls.initial_form_data = complete_form_data

    def test_valid_formset(self) -> None:
        good_form_data = self.initial_form_data.copy()
        # Choose 0 as our new mode since we know our fake
        # chant won't have been created with that mode.
        good_form_data["chant_set-0-mode"] = "0"
        res: Dict[str, Any] = save_browse_chants_formset.apply(
            args=(good_form_data, self.chant_ids)
        ).get()
        chant = self.chants[0]
        chant.refresh_from_db()
        self.assertEqual(chant.mode, "0")
        self.assertEqual(res["error_count"], 0)

    def test_invalid_formset(self) -> None:
        with self.subTest("Incomplete formset data"):
            bad_form_data = self.initial_form_data.copy()
            # Remove the form data for one of the chants.
            # The number of chants will then be out of sync with
            # the number of forms noted in the management form.
            for key in self.initial_form_data.keys():
                if key.startswith("chant_set-1"):
                    bad_form_data.pop(key)
            bad_form_data["chant_set-0-mode"] = "0"
            res = save_browse_chants_formset.apply(
                args=(bad_form_data, self.chant_ids)
            ).get()
            self.assertGreater(res["error_count"], 0)
            chant = self.chants[0]
            chant.refresh_from_db()
            self.assertNotEqual(chant.mode, "0")
        with self.subTest("Bad formset data: empty field"):
            bad_form_data = self.initial_form_data.copy()
            # Empty folio field should not be allowed
            bad_form_data["chant_set-0-folio"] = ""
            res = save_browse_chants_formset.apply(
                args=(bad_form_data, self.chant_ids)
            ).get()
            self.assertGreater(res["error_count"], 0)
            chant = self.chants[0]
            chant.refresh_from_db()
            self.assertNotEqual(chant.folio, "")
