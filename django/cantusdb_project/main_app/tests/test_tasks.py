from typing import List, Dict, Any
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.db.models import QuerySet

from main_app.tasks import save_browse_chants_formset, check_cantus_ids_not_in_ci, check_duplicate_folio_sequence, check_cantus_ids_genre_mismatch, check_position_service_mismatch
from main_app.tests.make_fakes import make_fake_source, make_fake_chant, make_fake_service
from main_app.models import Chant, Genre, Source
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
            chant = self.chants[0]
            chant.refresh_from_db()
            original_mode = chant.mode
            # Use a mode value distinct from the chant's current mode so we can
            # verify the invalid submission did not update the record.
            new_mode = "1" if original_mode != "1" else "2"
            bad_form_data["chant_set-0-mode"] = new_mode
            res = save_browse_chants_formset.apply(
                args=(bad_form_data, self.chant_ids)
            ).get()
            self.assertGreater(res["error_count"], 0)
            chant.refresh_from_db()
            self.assertEqual(chant.mode, original_mode)
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


class CheckCantusIdsNotInCiTest(TestCase):
    @patch("main_app.tasks.requests.get")
    def test_invalid_id_split_by_published(self, mock_get) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = '[{"cid":"001234"}]'
        mock_get.return_value = mock_resp

        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)
        pub_chant = make_fake_chant(source=pub_source, cantus_id="BADID")
        unpub_chant = make_fake_chant(source=unpub_source, cantus_id="BADID")
        valid_chant = make_fake_chant(source=pub_source, cantus_id="001234")

        result = check_cantus_ids_not_in_ci()
        self.assertIn(pub_chant, result["published"])
        self.assertIn(unpub_chant, result["unpublished"])
        self.assertNotIn(valid_chant, result["published"])


class CheckDuplicateFolioSequenceTest(TestCase):
    def test_duplicates_split_by_published(self) -> None:
        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)

        for source in (pub_source, unpub_source):
            make_fake_chant(source=source, folio="001r", c_sequence=1)
            Chant.objects.create(
                source=source,
                folio="001r",
                c_sequence=1,
                manuscript_full_text_std_spelling="test",
            )

        result = check_duplicate_folio_sequence()
        self.assertIn(pub_source.id, [g["source_id"] for g in result["published"]])
        self.assertIn(unpub_source.id, [g["source_id"] for g in result["unpublished"]])


class CheckCantusIdsGenreMismatchTest(TestCase):
    @patch("main_app.tasks.requests.get")
    def test_genre_mismatch_split_by_published(self, mock_get) -> None:
        # CI returns H for all IDs bulk fetch, and HV for the per-ID genre fetch
        def side_effect(url, **kwargs):
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            if "json-cids" in url:
                mock_resp.text = '[{"cid":"001234"}]'
            else:
                mock_resp.text = '{"info":{"field_genre":"HV"}}'
            return mock_resp

        mock_get.side_effect = side_effect

        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)
        pub_chant = make_fake_chant(source=pub_source, cantus_id="001234")
        unpub_chant = make_fake_chant(source=unpub_source, cantus_id="001234")
        # Set genre to H (mismatch with CI's HV)
        h_genre = Genre.objects.get_or_create(name="H", defaults={"description": "Hymn"})[0]
        pub_chant.genre = h_genre
        pub_chant.save()
        unpub_chant.genre = h_genre
        unpub_chant.save()

        result = check_cantus_ids_genre_mismatch([pub_chant.id, unpub_chant.id])
        self.assertIn(pub_chant, result["published"])
        self.assertIn(unpub_chant, result["unpublished"])


class CheckPositionServiceMismatchTest(TestCase):
    def test_position_service_mismatch_split_by_published(self) -> None:
        wrong_service = make_fake_service(name="M")  # Matins — not valid for B or M position
        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)

        pub_chant = make_fake_chant(source=pub_source, position="B", service=wrong_service)
        unpub_chant = make_fake_chant(source=unpub_source, position="M", service=wrong_service)

        valid_service = make_fake_service(name="L")
        valid_chant = make_fake_chant(source=pub_source, position="B", service=valid_service)

        result = check_position_service_mismatch([pub_chant.id, unpub_chant.id, valid_chant.id])
        self.assertIn(pub_chant, result["published"])
        self.assertIn(unpub_chant, result["unpublished"])
        self.assertNotIn(valid_chant, result["published"])
