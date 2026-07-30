import csv
import io
import zipfile
from typing import List, Dict, Any
from unittest.mock import patch, DEFAULT

from django.core import mail
from django.test import TestCase
from django.db.models import QuerySet

from main_app.tasks import (
    save_browse_chants_formset,
    check_cantus_ids_not_in_ci,
    check_duplicate_folio_sequence,
    check_cantus_ids_genre_mismatch,
    check_position_service_mismatch,
    check_blank_cantus_id,
    check_blank_mode,
    check_blank_invitatory_differentia,
    run_data_checks,
    _format_check_csv,
    PRODUCTION_BASE_URL,
    CHECK_LABELS,
)
from main_app.tests.make_fakes import (
    make_fake_source,
    make_fake_chant,
    make_fake_service,
    make_fake_genre,
    make_fake_user,
)
from main_app.models import Chant, DataCheckConfig, Genre, Source
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
    @patch("main_app.tasks.get_json_from_ci_api")
    def test_invalid_id_split_by_published(self, mock_get_json) -> None:
        mock_get_json.return_value = [{"cid": "001234"}]

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
    @patch("main_app.tasks.get_json_from_ci_api")
    def test_genre_mismatch_split_by_published(self, mock_get_json) -> None:
        # CI returns H for all IDs bulk fetch, and HV for the per-ID genre fetch
        def side_effect(path, **kwargs):
            if "json-cids" in path:
                return [{"cid": "001234"}]
            return {"info": {"field_genre": "HV"}}

        mock_get_json.side_effect = side_effect

        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)
        pub_chant = make_fake_chant(source=pub_source, cantus_id="001234")
        unpub_chant = make_fake_chant(source=unpub_source, cantus_id="001234")
        # Set genre to H (mismatch with CI's HV)
        h_genre = Genre.objects.get_or_create(
            name="H", defaults={"description": "Hymn"}
        )[0]
        pub_chant.genre = h_genre
        pub_chant.save()
        unpub_chant.genre = h_genre
        unpub_chant.save()

        result = check_cantus_ids_genre_mismatch([pub_chant.id, unpub_chant.id])
        self.assertIn(pub_chant, result["published"])
        self.assertIn(unpub_chant, result["unpublished"])

    @patch("main_app.tasks.get_json_from_ci_api")
    def test_genre_mismatch_with_multiple_local_genres_per_cantus_id(
        self, mock_get_json
    ) -> None:
        # Both chants share cantus_id "001234". CI reports its genre as "H".
        # One chant's local genre matches CI ("H"), the other doesn't ("R"),
        # so only the mismatching one should be flagged.
        def side_effect(path, **kwargs):
            if "json-cids" in path:
                return [{"cid": "001234"}]
            return {"info": {"field_genre": "H"}}

        mock_get_json.side_effect = side_effect

        source = make_fake_source(published=True)
        h_genre = Genre.objects.get_or_create(
            name="H", defaults={"description": "Hymn"}
        )[0]
        r_genre = Genre.objects.get_or_create(
            name="R", defaults={"description": "Responsory"}
        )[0]
        matching_chant = make_fake_chant(
            source=source, cantus_id="001234", genre=h_genre
        )
        mismatching_chant = make_fake_chant(
            source=source, cantus_id="001234", genre=r_genre
        )

        result = check_cantus_ids_genre_mismatch(
            [matching_chant.id, mismatching_chant.id]
        )
        self.assertIn(mismatching_chant, result["published"])
        self.assertNotIn(matching_chant, result["published"])


class CheckPositionServiceMismatchTest(TestCase):
    def test_position_service_mismatch_split_by_published(self) -> None:
        wrong_service = make_fake_service(
            name="M"
        )  # Matins — not valid for B or M position
        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)

        pub_chant = make_fake_chant(
            source=pub_source, position="B", service=wrong_service
        )
        unpub_chant = make_fake_chant(
            source=unpub_source, position="M", service=wrong_service
        )

        valid_service = make_fake_service(name="L")
        valid_chant = make_fake_chant(
            source=pub_source, position="B", service=valid_service
        )

        result = check_position_service_mismatch(
            [pub_chant.id, unpub_chant.id, valid_chant.id]
        )
        self.assertIn(pub_chant, result["published"])
        self.assertIn(unpub_chant, result["unpublished"])
        self.assertNotIn(valid_chant, result["published"])

    def test_position_service_mismatch_flags_null_service(self) -> None:
        pub_source = make_fake_source(published=True)
        no_service_chant = make_fake_chant(
            source=pub_source, position="M", service=None
        )

        result = check_position_service_mismatch([no_service_chant.id])
        self.assertIn(no_service_chant, result["published"])


class CheckBlankCantusIdTest(TestCase):
    def test_blank_cantus_id_split_by_published(self) -> None:
        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)
        pub_chant = make_fake_chant(source=pub_source, cantus_id="")
        unpub_chant = make_fake_chant(source=unpub_source, cantus_id="")
        valid_chant = make_fake_chant(source=pub_source, cantus_id="001234")

        result = check_blank_cantus_id([pub_chant.id, unpub_chant.id, valid_chant.id])
        self.assertIn(pub_chant, result["published"])
        self.assertIn(unpub_chant, result["unpublished"])
        self.assertNotIn(valid_chant, result["published"])


class CheckBlankModeTest(TestCase):
    def test_blank_mode_split_by_published(self) -> None:
        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)
        pub_chant = make_fake_chant(source=pub_source, mode="")
        unpub_chant = make_fake_chant(source=unpub_source, mode="")
        valid_chant = make_fake_chant(source=pub_source, mode="1")

        result = check_blank_mode([pub_chant.id, unpub_chant.id, valid_chant.id])
        self.assertIn(pub_chant, result["published"])
        self.assertIn(unpub_chant, result["unpublished"])
        self.assertNotIn(valid_chant, result["published"])


class CheckBlankInvitatoryDifferentiaTest(TestCase):
    def test_blank_differentia_on_invitatory_genres(self) -> None:
        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)
        genre_I = make_fake_genre(name="I")
        genre_IP = make_fake_genre(name="IP")
        other_genre = make_fake_genre(name="A")

        pub_chant = make_fake_chant(source=pub_source, genre=genre_I, differentia="")
        unpub_chant = make_fake_chant(
            source=unpub_source, genre=genre_IP, differentia=""
        )
        # invitatory with a differentia — should not appear
        valid_invitatory = make_fake_chant(
            source=pub_source, genre=genre_I, differentia="A"
        )
        # non-invitatory with blank differentia — should not appear
        non_invitatory = make_fake_chant(
            source=pub_source, genre=other_genre, differentia=""
        )

        result = check_blank_invitatory_differentia(
            [pub_chant.id, unpub_chant.id, valid_invitatory.id, non_invitatory.id]
        )
        self.assertIn(pub_chant, result["published"])
        self.assertIn(unpub_chant, result["unpublished"])
        self.assertNotIn(valid_invitatory, result["published"])
        self.assertNotIn(non_invitatory, result["published"])


class FormatCheckCsvTest(TestCase):
    def test_chant_row_links_to_chant_detail_and_flags_published(self) -> None:
        pub_source = make_fake_source(published=True)
        unpub_source = make_fake_source(published=False)
        pub_chant = make_fake_chant(source=pub_source, cantus_id="BADID")
        unpub_chant = make_fake_chant(source=unpub_source, cantus_id="BADID")

        content = _format_check_csv(
            {"published": [pub_chant], "unpublished": [unpub_chant]}
        )
        rows = list(csv.DictReader(io.StringIO(content)))

        pub_row = next(r for r in rows if r["chant_id"] == str(pub_chant.id))
        unpub_row = next(r for r in rows if r["chant_id"] == str(unpub_chant.id))

        expected_link = f'=HYPERLINK("{PRODUCTION_BASE_URL}/chant/{pub_chant.id}/","{pub_chant.id}")'
        self.assertEqual(pub_row["link"], expected_link)
        self.assertEqual(pub_row["published"], "1")
        self.assertEqual(unpub_row["published"], "0")

    def test_duplicate_group_row_links_to_source_folio(self) -> None:
        source = make_fake_source(published=True)
        make_fake_chant(source=source, folio="001r", c_sequence=1)
        Chant.objects.create(
            source=source,
            folio="001r",
            c_sequence=1,
            manuscript_full_text_std_spelling="test",
        )

        result = check_duplicate_folio_sequence()
        content = _format_check_csv(result)
        rows = list(csv.DictReader(io.StringIO(content)))

        row = next(r for r in rows if r["source_id"] == str(source.id))
        expected_link = (
            f'=HYPERLINK("{PRODUCTION_BASE_URL}/source/{source.id}/chants/?folio=001r","{source.id}")'
        )
        self.assertEqual(row["link"], expected_link)
        self.assertEqual(row["published"], "1")


class RunDataChecksTest(TestCase):
    def _patch_checks(self):
        empty_result = {"published": [], "unpublished": []}
        patcher = patch.multiple(
            "main_app.tasks",
            check_cantus_ids_not_in_ci=DEFAULT,
            check_duplicate_folio_sequence=DEFAULT,
            check_cantus_ids_genre_mismatch=DEFAULT,
            check_position_service_mismatch=DEFAULT,
            check_blank_cantus_id=DEFAULT,
            check_blank_mode=DEFAULT,
            check_blank_invitatory_differentia=DEFAULT,
        )
        mocks = patcher.start()
        self.addCleanup(patcher.stop)
        for mock in mocks.values():
            mock.return_value = empty_result
        return mocks

    def test_skips_everything_when_no_recipients(self) -> None:
        """When no recipients are configured, the check window is not
        consumed: no checks run and `last_run` is left untouched, so the
        full check runs once recipients are eventually added."""
        config = DataCheckConfig.objects.create(
            frequency=DataCheckConfig.Frequency.DAILY
        )

        mocks = self._patch_checks()
        run_data_checks.apply().get()

        mocks["check_blank_mode"].assert_not_called()
        self.assertEqual(len(mail.outbox), 0)
        config.refresh_from_db()
        self.assertIsNone(config.last_run)

    def test_sends_email_to_recipients_with_attachments(self) -> None:
        config = DataCheckConfig.objects.create(
            frequency=DataCheckConfig.Frequency.DAILY
        )
        recipient = make_fake_user(is_superuser=True)
        config.recipients.add(recipient)

        self._patch_checks()
        run_data_checks.apply().get()

        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, [recipient.email])
        self.assertEqual(len(sent.attachments), 1)
        filename, content, mimetype = sent.attachments[0]
        self.assertTrue(filename.endswith(".zip"))
        self.assertEqual(mimetype, "application/zip")
        with zipfile.ZipFile(io.BytesIO(content)) as zip_file:
            self.assertEqual(set(zip_file.namelist()), {f"{key}.csv" for key in CHECK_LABELS})
        config.refresh_from_db()
        self.assertIsNotNone(config.last_run)
