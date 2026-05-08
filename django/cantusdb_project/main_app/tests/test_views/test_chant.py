"""
Test views in views/chant.py
"""

from unittest.mock import patch
from unittest import skip
import random
from typing import ClassVar, Dict
import urllib.parse

from django.test import TestCase
from django.urls import reverse

from faker import Faker

from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_source,
    make_fake_volpiano,
    make_fake_service,
    make_fake_genre,
    make_fake_feast,
    make_fake_institution,
    make_random_string,
    get_random_search_term,
)
from main_app.tests.test_functions import mock_requests_get
from main_app.tests.mixins import CustomAccessTestMixin
from main_app.models import Chant, Source, Feast, Service
from main_app.views.chant import get_feast_selector_options


# Create a Faker instance with locale set to Latin
faker = Faker("la")


class ChantPermissionsTestCase(CustomAccessTestMixin, TestCase):
    chants: Dict[str, Chant]

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        fake_cantus_id = faker.numerify("######")
        published_source = make_fake_source(published=True)
        published_chant = make_fake_chant(
            source=published_source, cantus_id=fake_cantus_id
        )
        editor_assigned_source = make_fake_source(
            published=False, current_editors=[cls.users["editor"]]
        )
        editor_assigned_chant = make_fake_chant(
            source=editor_assigned_source, cantus_id=fake_cantus_id
        )
        user_assigned_source = make_fake_source(
            published=False, current_editors=[cls.users["user"]]
        )
        user_assigned_chant = make_fake_chant(
            source=user_assigned_source, cantus_id=fake_cantus_id
        )
        unassigned_source = make_fake_source(published=False)
        unassigned_chant = make_fake_chant(
            source=unassigned_source, cantus_id=fake_cantus_id
        )
        cls.chants = {
            "published_chant": published_chant,
            "editor_assigned_chant": editor_assigned_chant,
            "user_assigned_chant": user_assigned_chant,
            "unassigned_chant": unassigned_chant,
        }


class ChantDetailViewTest(ChantPermissionsTestCase):

    def test_url_and_templates(self) -> None:
        chant = make_fake_chant()
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_detail.html")

    def test_context_folios(self) -> None:
        # create a source and several chants in it
        source = make_fake_source()
        chant = make_fake_chant(source=source, folio="001r")
        make_fake_chant(source=source, folio="001r")
        make_fake_chant(source=source, folio="001v")
        make_fake_chant(source=source, folio="001v")
        make_fake_chant(source=source, folio="002r")
        make_fake_chant(source=source, folio="002v")
        # request the page
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        # the element in "folios" should be unique and ordered in this way
        folios = response.context["folios"]
        self.assertEqual(list(folios), ["001r", "001v", "002r", "002v"])

    def test_context_previous_and_next_folio(self) -> None:
        # create a source and several chants in it
        source = make_fake_source()
        # three folios: 001r, 001v, 002r
        chant_without_previous_folio = make_fake_chant(source=source, folio="001r")
        chant_with_previous_and_next_folio = make_fake_chant(
            source=source, folio="001v"
        )
        chant_without_next_folio = make_fake_chant(source=source, folio="002v")
        # request the page and check the context variables
        # for the chant on 001r, there is no previous folio, and the next folio should be 001v
        response = self.client.get(
            reverse("chant-detail", args=[chant_without_previous_folio.id])
        )
        self.assertIsNone(response.context["previous_folio"])
        self.assertEqual(response.context["next_folio"], "001v")

        # for the chant on 001v, previous folio should be 001r, and next folio should be 002v
        response = self.client.get(
            reverse("chant-detail", args=[chant_with_previous_and_next_folio.id])
        )
        self.assertEqual(response.context["previous_folio"], "001r")
        self.assertEqual(response.context["next_folio"], "002v")

        # for the chant on 002v, there is no next folio, and the previous folio should be 001v
        response = self.client.get(
            reverse("chant-detail", args=[chant_without_next_folio.id])
        )
        self.assertEqual(response.context["previous_folio"], "001v")
        self.assertIsNone(response.context["next_folio"])

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse("chant-detail", args=[self.chants["published_chant"].id]),
            get_allowed_users=[
                "superuser",
                "anonymous user",
                "global viewer",
                "editor",
                "user",
            ],
            post_allowed_users=[],
            test_name="Published chant",
        )
        self.run_request_permissions_test(
            url=reverse("chant-detail", args=[self.chants["editor_assigned_chant"].id]),
            get_allowed_users=["superuser", "global viewer", "editor"],
            post_allowed_users=[],
            test_name="Editor assigned chant",
        )
        self.run_request_permissions_test(
            url=reverse("chant-detail", args=[self.chants["user_assigned_chant"].id]),
            get_allowed_users=["superuser", "global viewer", "user"],
            post_allowed_users=[],
            test_name="User assigned chant",
        )
        self.run_request_permissions_test(
            url=reverse("chant-detail", args=[self.chants["unassigned_chant"].id]),
            get_allowed_users=["superuser", "global viewer"],
            post_allowed_users=[],
            test_name="Unassigned chant",
        )

    def test_chant_edit_link(self) -> None:
        source = make_fake_source()
        chant = make_fake_chant(source=source, folio="001r")

        self.client.force_login(self.users["superuser"])

        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        expected_url_fragment = (
            f"edit-chants/{source.id}?pk={chant.id}&folio={chant.folio}"
        )

        self.assertIn(expected_url_fragment, str(response.content))

    def test_chant_with_volpiano_with_no_fulltext(self) -> None:
        # in the past, a Chant Detail page will error rather than loading
        # properly when the chant has volpiano but no fulltext
        source = make_fake_source()
        chant = make_fake_chant(
            source=source,
            volpiano="1---c--g--e---e---d---c---c---f---e---e--d---d---c",
            manuscript_full_text=None,
            manuscript_full_text_std_spelling=None,
        )

        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        self.assertEqual(response.status_code, 200)

    def test_chant_with_volpiano_with_no_incipit(self) -> None:
        # in the past, a Chant Detail page will error rather than loading properly
        # when the chant has volpiano but no fulltext/incipit
        source = make_fake_source()
        chant = make_fake_chant(
            source=source,
            volpiano="1---g---a---g--a---g---e---c--e---|---f---g--f--g---f--d---9--d",
        )
        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.incipit = None
        chant.save()
        response = self.client.get(reverse("chant-detail", args=[chant.id]))
        self.assertEqual(response.status_code, 200)

    def test_json_response(self) -> None:
        chant = make_fake_chant()
        response = self.client.get(
            reverse("chant-detail", args=[chant.id]), HTTP_ACCEPT="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        resp_chant = response.json()["chant"]
        self.assertEqual(resp_chant["id"], chant.id)
        self.assertEqual(resp_chant["manuscript_full_text"], chant.manuscript_full_text)


class SourceEditChantsViewTest(ChantPermissionsTestCase):
    default_user = "superuser"

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse(
                "source-edit-chants", args=[self.chants["published_chant"].source.id]
            ),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="Published chant",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-edit-chants",
                args=[self.chants["editor_assigned_chant"].source.id],
            ),
            get_allowed_users=["superuser", "editor"],
            post_allowed_users=["superuser", "editor"],
            test_name="Editor assigned chant",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-edit-chants",
                args=[self.chants["user_assigned_chant"].source.id],
            ),
            get_allowed_users=["superuser", "user"],
            post_allowed_users=["superuser", "user"],
            test_name="User assigned chant",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-edit-chants", args=[self.chants["unassigned_chant"].source.id]
            ),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="Unassigned chant",
        )

    def test_url_and_templates(self):
        source1 = make_fake_source()

        # must specify folio, or SourceEditChantsView.get_queryset will fail when it tries to default to displaying the first folio
        make_fake_chant(source=source1, folio="001r")

        with patch("requests.get", mock_requests_get):
            response = self.client.get(reverse("source-edit-chants", args=[source1.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")
        response = self.client.get(
            reverse("source-edit-chants", args=[source1.id + 100])
        )
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

        # trying to access chant-edit with a source that has no chant should return 200
        source2 = make_fake_source()
        with patch("requests.get", mock_requests_get):
            response = self.client.get(reverse("source-edit-chants", args=[source2.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")

    def test_update_chant(self):
        source = make_fake_source()
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="initial"
        )
        response = self.client.get(
            reverse("source-edit-chants", args=[source.id]), {"pk": chant.id}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_edit.html")

        folio = chant.folio
        c_sequence = chant.c_sequence
        response = self.client.post(
            reverse("source-edit-chants", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "test",
                "pk": chant.id,
                "folio": folio,
                "c_sequence": c_sequence,
            },
        )
        self.assertEqual(response.status_code, 302)
        # Check that after the edit, the user is redirected to the source-edit-chants page
        self.assertRedirects(response, reverse("source-edit-chants", args=[source.id]))
        chant.refresh_from_db()
        self.assertEqual(chant.manuscript_full_text_std_spelling, "test")

    def test_volpiano_signal(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="ut queant lactose",
            source=source,
            folio="001r",
            c_sequence=1,
        )
        self.client.post(
            reverse("source-edit-chants", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "ut queant lactose",
                "pk": chant_1.id,
                "folio": "001r",
                "c_sequence": "1",
                # liquescents, to be converted to lowercase
                #                    vv v v v v v v
                "volpiano": "9abcdefg)A-B1C2D3E4F5G67?. yiz",
                #                      ^ ^ ^ ^ ^ ^ ^^^^^^^^
                # clefs, accidentals, etc., to be deleted
            },
        )
        chant_1 = Chant.objects.get(
            manuscript_full_text_std_spelling="ut queant lactose"
        )
        self.assertEqual(chant_1.volpiano, "9abcdefg)A-B1C2D3E4F5G67?. yiz")
        self.assertEqual(chant_1.volpiano_notes, "9abcdefg9abcdefg")

        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="resonare foobaz",
            source=source,
            folio="001r",
            c_sequence=2,
        )
        expected_volpiano: str = "abacadaeafagahaja"
        expected_intervals: str = "1-12-23-34-45-56-67-78-8"
        self.client.post(
            reverse("source-edit-chants", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "resonare foobaz",
                "folio": "001r",
                "c_sequence": "2",
                "volpiano": "abacadaeafagahaja",
                "pk": chant_2.id,
            },
        )
        chant_2 = Chant.objects.get(manuscript_full_text_std_spelling="resonare foobaz")
        self.assertEqual(chant_2.volpiano, expected_volpiano)
        self.assertEqual(chant_2.volpiano_intervals, expected_intervals)

    def test_chant_with_volpiano_with_no_fulltext(self):
        # in the past, a Chant Edit page will error rather than loading properly when the chant has volpiano but no fulltext
        source = make_fake_source()
        chant = make_fake_chant(source=source, volpiano="1---f--e---f--d---e--c---d--d")
        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.save()
        response = self.client.get(
            reverse("source-edit-chants", args=[source.id]), {"pk": chant.id}
        )
        self.assertEqual(response.status_code, 200)

    def test_chant_with_volpiano_with_no_incipit(self):
        # in the past, a Chant Edit page will error rather than loading properly when the chant has volpiano but no fulltext/incipit
        source = make_fake_source()
        chant = make_fake_chant(
            source=source,
            volpiano="1---d---da--g--f--e---e-eg--fed---d-nmn-mn---d",
        )
        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.incipit = None
        chant.save()
        response = self.client.get(
            reverse("source-edit-chants", args=[source.id]), {"pk": chant.id}
        )
        self.assertEqual(response.status_code, 200)

    def test_proofread_chant(self):
        chant = make_fake_chant(
            manuscript_full_text_std_spelling="lorem ipsum",
            folio="001r",
            manuscript_full_text_std_proofread=False,
        )
        folio = chant.folio
        c_sequence = chant.c_sequence
        ms_std = chant.manuscript_full_text_std_spelling
        self.assertIs(chant.manuscript_full_text_std_proofread, False)
        source = chant.source
        response = self.client.post(
            reverse("source-edit-chants", args=[source.id]),
            {
                "manuscript_full_text_std_proofread": "True",
                "folio": folio,
                "c_sequence": c_sequence,
                "manuscript_full_text_std_spelling": ms_std,
                "pk": chant.id,
            },
        )
        self.assertEqual(response.status_code, 302)  # 302 Found
        chant.refresh_from_db()
        self.assertIs(chant.manuscript_full_text_std_proofread, True)

    @skip("Temporarily disabled due to #1674")
    def test_invalid_text(self) -> None:
        """
        The user should not be able to create a chant with invalid text
        (either invalid characters or unmatched brackets).
        Instead, the user should be shown an error message.
        """
        source = make_fake_source()
        with self.subTest("Chant with invalid characters"):
            response = self.client.post(
                reverse("source-edit-chants", args=[source.id]),
                {
                    "manuscript_full_text_std_spelling": "this is a ch@nt t%xt with inv&lid ch!ra+ers",
                    "folio": "001r",
                    "c_sequence": "1",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertFormError(
                response.context["form"],
                "manuscript_full_text_std_spelling",
                "Invalid characters in text.",
            )
        with self.subTest("Chant with unmatched brackets"):
            response = self.client.post(
                reverse("source-edit-chants", args=[source.id]),
                {
                    "manuscript_full_text_std_spelling": "this is a chant with [ unmatched brackets",
                    "folio": "001r",
                    "c_sequence": "1",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertFormError(
                response.context["form"],
                "manuscript_full_text_std_spelling",
                "Word [ contains non-alphabetic characters.",
            )

    def test_full_text_requirement(self):
        """
        When editing a chant, we generally require a full text to be provided
        (this is also true when creating a chant); however, some chants were
        created before this was required and so may not have full text. In
        these cases, the user should be allowed to save edits to a chant (for
        example, a correction to another field) without having to provide a
        full text.
        """
        source = make_fake_source()
        with self.subTest("Chant with full text"):
            chant_w_fulltext = make_fake_chant(
                source=source, manuscript_full_text_std_spelling="Plena sum", mode=None
            )
            response = self.client.post(
                reverse("source-edit-chants", args=[source.id]),
                {
                    "manuscript_full_text_std_spelling": "",
                    "folio": chant_w_fulltext.folio,
                    "c_sequence": chant_w_fulltext.c_sequence,
                    "pk": chant_w_fulltext.id,
                    "mode": "2",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertFormError(
                response.context["form"],
                "manuscript_full_text_std_spelling",
                "This field cannot be blank for this chant.",
            )
            self.assertEqual(response.context["form"]["mode"].data, "2")
            self.assertEqual(
                response.context["form"]["manuscript_full_text_std_spelling"].data,
                "Plena sum",
            )
            chant_w_fulltext.refresh_from_db()
            self.assertEqual(
                chant_w_fulltext.manuscript_full_text_std_spelling, "Plena sum"
            )
            self.assertIsNone(chant_w_fulltext.mode)
        with self.subTest("Chant with no full text"):
            chant_wo_fulltext = make_fake_chant(
                source=source, manuscript_full_text_std_spelling=None, mode="1"
            )
            response = self.client.post(
                reverse("source-edit-chants", args=[source.id]),
                {
                    "folio": chant_wo_fulltext.folio,
                    "c_sequence": chant_wo_fulltext.c_sequence,
                    "pk": chant_wo_fulltext.id,
                    "mode": "2",
                },
            )
            self.assertEqual(response.status_code, 302)
            chant_wo_fulltext.refresh_from_db()
            self.assertEqual(chant_wo_fulltext.mode, "2")
            self.assertEqual(chant_wo_fulltext.manuscript_full_text, "")


class ChantEditSyllabificationViewTest(ChantPermissionsTestCase):
    default_user = "superuser"

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse(
                "source-edit-syllabification", args=[self.chants["published_chant"].id]
            ),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="Published chant",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-edit-syllabification",
                args=[self.chants["editor_assigned_chant"].id],
            ),
            get_allowed_users=["superuser", "editor"],
            post_allowed_users=["superuser", "editor"],
            test_name="Editor assigned chant",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-edit-syllabification",
                args=[self.chants["user_assigned_chant"].id],
            ),
            get_allowed_users=["superuser", "user"],
            post_allowed_users=["superuser", "user"],
            test_name="User assigned chant",
        )
        self.run_request_permissions_test(
            url=reverse(
                "source-edit-syllabification", args=[self.chants["unassigned_chant"].id]
            ),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="Unassigned chant",
        )

    def test_view_url_and_templates(self):
        chant = make_fake_chant()
        chant_id = chant.id

        response_1 = self.client.get(f"/edit-syllabification/{chant_id}")
        self.assertEqual(response_1.status_code, 200)
        self.assertTemplateUsed(response_1, "base.html")
        self.assertTemplateUsed(response_1, "chant_syllabification_edit.html")

        response_2 = self.client.get(
            reverse("source-edit-syllabification", args=[chant_id])
        )
        self.assertEqual(response_2.status_code, 200)

        self.client.logout()
        response_3 = self.client.get(
            reverse("source-edit-syllabification", args=[chant_id])
        )
        self.assertEqual(response_3.status_code, 302)  # 302: redirect to login page

    def test_edit_syllabification(self):
        chant = make_fake_chant(manuscript_syllabized_full_text="lorem ipsum")
        self.assertEqual(chant.manuscript_syllabized_full_text, "lorem ipsum")
        response = self.client.post(
            f"/edit-syllabification/{chant.id}",
            {
                "manuscript_full_text": "lorem ipsum",
                "manuscript_syllabized_full_text": "lore-m i-psum",
            },
        )
        self.assertEqual(response.status_code, 302)  # 302 Found
        chant.refresh_from_db()
        self.assertEqual(chant.manuscript_syllabized_full_text, "lore-m i-psum")


class ChantByCantusIDViewTest(ChantPermissionsTestCase):
    def test_url_and_templates(self):
        chant = make_fake_chant()
        response = self.client.get(
            reverse("chant-by-cantus-id", args=[chant.cantus_id])
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_seq_by_cantus_id.html")

    def test_queryset(self):
        chant = make_fake_chant()
        response = self.client.get(
            reverse("chant-by-cantus-id", args=[chant.cantus_id])
        )
        self.assertIn(chant, response.context["chants"])

    def test_permissions(self) -> None:
        # Chants in self.chants all have the same Cantus ID
        cantus_id = self.chants["published_chant"].cantus_id
        all_chants = self.chants.values()
        with self.subTest("Anonymous user"):
            response = self.client.get(reverse("chant-by-cantus-id", args=[cantus_id]))
            listed_chants = response.context["chants"]
            self.assertCountEqual([self.chants["published_chant"]], listed_chants)
        with self.subTest("Global viewer"):
            self.client.force_login(self.users["global viewer"])
            response = self.client.get(reverse("chant-by-cantus-id", args=[cantus_id]))
            listed_chants = response.context["chants"]
            self.assertCountEqual(all_chants, listed_chants)
        with self.subTest("Superuser"):
            self.client.force_login(self.users["superuser"])
            response = self.client.get(reverse("chant-by-cantus-id", args=[cantus_id]))
            listed_chants = response.context["chants"]
            self.assertCountEqual(all_chants, listed_chants)
        with self.subTest("Editor"):
            self.client.force_login(self.users["editor"])
            response = self.client.get(reverse("chant-by-cantus-id", args=[cantus_id]))
            listed_chants = response.context["chants"]
            self.assertCountEqual(
                [self.chants["published_chant"], self.chants["editor_assigned_chant"]],
                listed_chants,
            )
        with self.subTest("User"):
            self.client.force_login(self.users["user"])
            response = self.client.get(reverse("chant-by-cantus-id", args=[cantus_id]))
            listed_chants = response.context["chants"]
            self.assertCountEqual(
                [self.chants["published_chant"], self.chants["user_assigned_chant"]],
                listed_chants,
            )


class ChantSearchViewTest(CustomAccessTestMixin, TestCase):
    def test_view_url_path(self):
        response = self.client.get("/chant-search/")
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        response = self.client.get(reverse("chant-search"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_search.html")

    def test_permissions(self) -> None:
        # We create the desired chants here, rather than using
        # the ChantPermissionsTestCase because we want these additions
        # rolled back before other tests in this class.
        published_chant = make_fake_chant(source=make_fake_source(published=True))
        cantus_id = published_chant.cantus_id
        editor_assigned_chant = make_fake_chant(
            source=make_fake_source(
                published=False, current_editors=[self.users["editor"]]
            ),
            cantus_id=cantus_id,
        )
        user_assigned_chant = make_fake_chant(
            source=make_fake_source(
                published=False, current_editors=[self.users["user"]]
            ),
            cantus_id=cantus_id,
        )
        unassigned_chant = make_fake_chant(
            source=make_fake_source(published=False), cantus_id=cantus_id
        )
        all_chants = [
            published_chant,
            editor_assigned_chant,
            user_assigned_chant,
            unassigned_chant,
        ]
        with self.subTest("Anonymous user"):
            response = self.client.get(
                reverse("chant-search"), {"cantus_id": cantus_id}
            )
            listed_chants = response.context["chants"]
            self.assertCountEqual([published_chant], listed_chants)
        with self.subTest("Global viewer"):
            self.client.force_login(self.users["global viewer"])
            response = self.client.get(
                reverse("chant-search"), {"cantus_id": cantus_id}
            )
            listed_chants = response.context["chants"]
            self.assertCountEqual(all_chants, listed_chants)
        with self.subTest("Superuser"):
            self.client.force_login(self.users["superuser"])
            response = self.client.get(
                reverse("chant-search"), {"cantus_id": cantus_id}
            )
            listed_chants = response.context["chants"]
            self.assertCountEqual(all_chants, listed_chants)
        with self.subTest("Editor"):
            self.client.force_login(self.users["editor"])
            response = self.client.get(
                reverse("chant-search"), {"cantus_id": cantus_id}
            )
            listed_chants = response.context["chants"]
            self.assertCountEqual(
                [published_chant, editor_assigned_chant],
                listed_chants,
            )
        with self.subTest("User"):
            self.client.force_login(self.users["user"])
            response = self.client.get(
                reverse("chant-search"), {"cantus_id": cantus_id}
            )
            listed_chants = response.context["chants"]
            self.assertCountEqual(
                [published_chant, user_assigned_chant],
                listed_chants,
            )

    def test_search_by_service(self):
        source = make_fake_source(published=True)
        service = make_fake_service()
        chant = make_fake_chant(source=source, service=service)
        search_term = service.id
        response = self.client.get(reverse("chant-search"), {"service": search_term})
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_filter_by_genre(self):
        source = make_fake_source(published=True)
        genre = make_fake_genre()
        chant = make_fake_chant(source=source, genre=genre)
        response = self.client.get(reverse("chant-search"), {"genre": genre.id})
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_cantus_id(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source, cantus_id=faker.numerify("######"))
        search_term = get_random_search_term(chant.cantus_id)
        response = self.client.get(reverse("chant-search"), {"cantus_id": search_term})
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_mode(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source, mode=faker.numerify("#"))
        search_term = get_random_search_term(chant.mode)
        response = self.client.get(reverse("chant-search"), {"mode": search_term})
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_feast(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast()
        chant = make_fake_chant(source=source, feast=feast)
        search_term = get_random_search_term(feast.name)
        response = self.client.get(reverse("chant-search"), {"feast": search_term})
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_position(self):
        source = make_fake_source(published=True)
        position = 1
        chant = make_fake_chant(source=source, position=position)
        search_term = "1"
        response = self.client.get(reverse("chant-search"), {"position": search_term})
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_filter_by_melody(self):
        source = make_fake_source(published=True)
        chant_with_melody = make_fake_chant(
            source=source,
            volpiano=make_fake_volpiano(),
        )
        # Create a chant without a melody
        make_fake_chant(source=source, volpiano=None)
        response = self.client.get(reverse("chant-search"), {"melodies": "true"})
        # only chants with melodies should be in the result
        self.assertEqual(len(response.context["chants"]), 1)
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(context_chant_id, chant_with_melody.id)

    def test_keyword_search_starts_with(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=faker.sentence(),
        )
        # use the beginning part of the full text as the search term
        search_term = chant.manuscript_full_text_std_spelling[
            0 : random.randint(1, len(chant.manuscript_full_text_std_spelling))
        ]
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "starts_with"}
        )
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_keyword_search_contains(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(
            source=source,
            manuscript_full_text="hoc tantum possum dicere",
        )
        search_term = "tantum possum"
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_search_bar_search(self):
        # note to developers: if you are changing the behavior of search_bar
        # searches, be sure to check static/js/chant_search.js to see if it needs
        # updating (among other things, this script populates the search fields on
        # the Chant Search page if a user arrives via the Global Search Bar)
        chant_with_incipit_only = make_fake_chant(
            manuscript_full_text="The first three*", cantus_id="987654"
        )
        chant_with_full_text = make_fake_chant(
            manuscript_full_text="The entire text is present for this one",
            cantus_id="098765",
        )
        chant_with_ascending_cantus_id = make_fake_chant(
            manuscript_full_text="Full text contains, but does not start with 'the'",
            cantus_id="123456",
        )
        # Create a chant starting with a number that won't be found by either
        # search term
        make_fake_chant(
            manuscript_full_text=(
                "1 is a number. How unusual, to find an arabic numeral in a chant!"
            ),
            cantus_id="234567",
        )

        # if the search term contains no numerals, we should be doing an incipit
        # search. Non-letter, non-numeral characters like "*" should not cause
        # a switch to searching by Cantus ID
        full_incipit_search_term = "the first three*"
        response_1 = self.client.get(
            reverse("chant-search"), {"search_bar": full_incipit_search_term}
        )
        context_chants_1 = response_1.context["chants"]
        self.assertEqual(len(context_chants_1), 1)
        context_chant_1_id = context_chants_1[0].id
        self.assertEqual(context_chant_1_id, chant_with_incipit_only.id)

        short_incipit_search_term = "the"
        response_2 = self.client.get(
            reverse("chant-search"), {"search_bar": short_incipit_search_term}
        )
        context_chants_2 = response_2.context["chants"]
        self.assertEqual(len(context_chants_2), 2)
        context_chants_2_ids = context_chants_2[0].id, context_chants_2[1].id
        self.assertIn(chant_with_incipit_only.id, context_chants_2_ids)
        self.assertIn(chant_with_full_text.id, context_chants_2_ids)
        self.assertNotIn(chant_with_ascending_cantus_id.id, context_chants_2_ids)

        # if the search term contains even a single numeral, we should be doing
        # a Cantus ID search
        numeric_search_term = "1"
        response_3 = self.client.get(
            reverse("chant-search"), {"search_bar": numeric_search_term}
        )
        context_chants_3 = response_3.context["chants"]
        self.assertEqual(len(context_chants_3), 1)
        context_chant_3_id = context_chants_3[0].id
        self.assertEqual(context_chant_3_id, chant_with_ascending_cantus_id.id)

        letters_and_numbers_search_term = "1 is"
        response_4 = self.client.get(
            reverse("chant-search"), {"search_bar": letters_and_numbers_search_term}
        )
        context_chants_4 = response_4.context["chants"]
        self.assertEqual(len(context_chants_4), 0)

    def test_order_by_siglum(self):
        hinst_1 = make_fake_institution(siglum="AA-Bb")
        source_1 = make_fake_source(
            published=True, shelfmark="sigl-1", holding_institution=hinst_1
        )
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="thing 1", source=source_1
        )

        hinst_2 = make_fake_institution(siglum="BB-Cc")
        source_2 = make_fake_source(
            published=True, shelfmark="sigl-2", holding_institution=hinst_2
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="thing 2", source=source_2
        )

        search_term = "thing"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "siglum",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "siglum",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_siglum_global_search(self):
        hinst_1 = make_fake_institution(siglum="AA-Bb")
        source_1 = make_fake_source(
            published=True, shelfmark="sigl-1", holding_institution=hinst_1
        )
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="thing 1", source=source_1
        )

        hinst_2 = make_fake_institution(siglum="BB-Cc")
        source_2 = make_fake_source(
            published=True, shelfmark="sigl-2", holding_institution=hinst_2
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="thing 2", source=source_2
        )
        search_term = "thing"
        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "siglum",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "siglum",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_incipit(self):
        source = make_fake_source(published=True)
        chant_1 = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="higgledy"
        )
        chant_2 = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="piggledy"
        )

        search_term = "iggl"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "incipit",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "incipit",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_feast(self):
        source = make_fake_source(published=True)
        feast1 = make_fake_feast(name="A")
        feast2 = make_fake_feast(name="B")
        chant_1 = make_fake_chant(source=source, feast=feast1)
        chant_2 = make_fake_chant(source=source, feast=feast2)

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "order": "feast",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_feast = ascending_results[0].feast
        self.assertEqual(first_result_feast, chant_1.feast)
        last_result_feast = ascending_results[1].feast
        self.assertEqual(last_result_feast, chant_2.feast)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "order": "feast",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_feast = descending_results[0].feast
        self.assertEqual(first_result_feast, chant_2.feast)
        last_result_feast = descending_results[1].feast
        self.assertEqual(last_result_feast, chant_1.feast)

    def test_order_by_incipit_global_search(self):
        source = make_fake_source(published=True)
        chant_1 = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="jiggle"
        )
        chant_2 = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="jigsaw"
        )

        search_term = "jig"
        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "incipit",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "incipit",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_service(self):
        # currently, service sort works by ID rather than by name
        service_1 = make_fake_service(name="A")
        service_2 = make_fake_service(name="B")

        chant_1 = make_fake_chant(
            service=service_1, manuscript_full_text_std_spelling="hocus"
        )
        chant_2 = make_fake_chant(
            service=service_2, manuscript_full_text_std_spelling="pocus"
        )

        search_term = "ocu"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "service",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "service",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_service_global_search(self):
        # currently, service sort works by ID rather than by name
        service_1 = make_fake_service(name="A")
        service_2 = make_fake_service(name="B")
        chant_1 = make_fake_chant(
            service=service_1, manuscript_full_text_std_spelling="fluffy"
        )
        chant_2 = make_fake_chant(
            service=service_2, manuscript_full_text_std_spelling="fluster"
        )

        search_term = "flu"
        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "service",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "service",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_genre(self):
        # currently, genre sort works by ID rather than by name
        genre_1 = make_fake_genre(name="A")
        genre_2 = make_fake_genre(name="B")
        chant_1 = make_fake_chant(
            genre=genre_1, manuscript_full_text_std_spelling="hocus"
        )
        chant_2 = make_fake_chant(
            genre=genre_2, manuscript_full_text_std_spelling="focus"
        )

        search_term = "ocu"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "genre",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "genre",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_genre_global_search(self):
        # currently, genre sort works by ID rather than by name
        genre_1 = make_fake_genre(name="A")
        genre_2 = make_fake_genre(name="B")
        chant_1 = make_fake_chant(
            genre=genre_1, manuscript_full_text_std_spelling="chuckle"
        )
        chant_2 = make_fake_chant(
            genre=genre_2, manuscript_full_text_std_spelling="chunky"
        )

        search_term = "chu"
        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "genre",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "genre",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_cantus_id(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="isaac", cantus_id="121393"
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="baal", cantus_id="196418"
        )

        search_term = "aa"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "cantus_id",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "cantus_id",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_cantus_id_global_search(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="twinkle", cantus_id="121393"
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="twirl", cantus_id="196413"
        )

        search_term = "13"
        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "cantus_id",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "cantus_id",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_mode(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="For first he looks upon his forepaws to see if they are clean",
            mode="1",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="For secondly he kicks up behind to clear away there",
            mode="2",
        )

        search_term = "for"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "mode",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "mode",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_mode_global_search(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="doodle",
            mode="1",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="doodad",
            mode="2",
        )

        search_term = "doo"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "mode",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "mode",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_ms_fulltext(self):
        chant_1 = make_fake_chant(
            manuscript_full_text="this is a chant with a MS spelling fylltexte",
            manuscript_full_text_std_spelling="this is a chant with a MS spelling fulltext",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="this will become a chant without a MS spelling fulltext",
        )
        chant_2.manuscript_full_text = ""
        chant_2.save()

        search_term = "a chant wit"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_fulltext",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_fulltext",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_ms_fulltext_global_search(self):
        chant_1 = make_fake_chant(
            manuscript_full_text="this is a chant with a MS spelling fylltexte",
            manuscript_full_text_std_spelling="this is a chant with a MS spelling fulltext",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="this will become a chant without a MS spelling fulltext",
        )
        chant_2.manuscript_full_text = ""
        chant_2.save()

        search_term = "this"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "has_fulltext",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "has_fulltext",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_volpiano(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant with volpiano",
            volpiano="1---d---d---a--a---a---e--f--e---d---4",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant about parsley",
        )
        chant_2.volpiano = ""
        chant_2.save()

        search_term = "s is a ch"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_melody",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_melody",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_volpiano_global_search(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant with volpiano",
            volpiano="1---d---d---a--a---a---e--f--e---d---4",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant about mushrooms",
        )
        chant_2.volpiano = ""
        chant_2.save()

        search_term = "this is a chant"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "has_melody",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "has_melody",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_image_link(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant with a link",
            image_link="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant without",
        )
        chant_2.image_link = ""
        chant_2.save()

        search_term = "a chant with"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_image",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_image",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_image_link_global_search(self):
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant with a link",
            image_link="https://www.youtube.com/watch?v=hyCIpKAIFyo",
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant without",
        )
        chant_2.image_link = ""
        chant_2.save()

        search_term = "this is"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "has_image",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
                "order": "has_image",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_nulls_last(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast(name="A")

        chant_with_feast = make_fake_chant(source=source, feast=feast)
        chant_without_feast = make_fake_chant(source=source, feast=None)

        # Ascending sort — null should be last
        response_asc = self.client.get(
            reverse("chant-search"),
            {
                "order": "feast",
                "sort": "asc",
            },
        )
        ascending_results = response_asc.context["chants"]
        self.assertIn(chant_with_feast, ascending_results)
        self.assertIn(chant_without_feast, ascending_results)

        self.assertEqual(ascending_results[0].feast, feast)
        self.assertIsNone(ascending_results[1].feast)

        # Descending sort — null should still be last
        response_desc = self.client.get(
            reverse("chant-search"),
            {
                "order": "feast",
                "sort": "desc",
            },
        )
        descending_results = response_desc.context["chants"]
        self.assertEqual(descending_results[0].feast, feast)
        self.assertIsNone(descending_results[1].feast)

    def test_column_header_links(self):
        # these are the 10 column headers users can order by:
        shelfmark = "glum-01"
        fulltext = "so it begins"
        feast = make_fake_feast()
        service = make_fake_service()
        genre = make_fake_genre()
        cantus_id = make_random_string(6, "0123456789")
        mode = make_random_string(1, "0123456789*?")
        mel = make_fake_volpiano()
        image = faker.image_url()

        source = make_fake_source(shelfmark=shelfmark, published=True)

        # additional properties for which there are search fields
        position = make_random_string(1)
        make_fake_chant(
            manuscript_full_text_std_spelling=fulltext,
            service=service,
            genre=genre,
            cantus_id=cantus_id,
            mode=mode,
            volpiano=mel,
            image_link=image,
            source=source,
            feast=feast,
            position=position,
        )
        search_term = "so it be"

        response_1 = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
            },
        )
        html_1 = str(response_1.content)
        # if no ordering specified, all 10 links should include "&sort=asc"
        self.assertEqual(html_1.count("&sort=asc"), 10)

        # test that all query parameters are present in all 10 links
        query_keys_and_values = {
            "op": "contains",
            "keyword": search_term,
            "service": service.id,
            "genre": genre.id,
            "cantus_id": cantus_id,
            "mode": mode,
            "feast": feast.name,
            "position": position,
            "melodies": "true",
        }

        response_2 = self.client.get(
            reverse("chant-search"),
            query_keys_and_values,
        )
        html_2 = str(response_2.content)

        for k, v in query_keys_and_values.items():
            # Generate URL-encoded parameter with + for spaces (how Django's urlencode works)
            v_str = str(v)
            encoded_param = urllib.parse.quote_plus(v_str)
            expected_query_param = f"{k}={encoded_param}"

            # Assert that it appears 10 times
            self.assertEqual(html_2.count(expected_query_param), 10)

        # Test search_bar in the same way
        response_3 = self.client.get(
            reverse("chant-search"),
            {
                "search_bar": search_term,
            },
        )
        html_3 = str(response_3.content)

        # Use quote_plus to encode with + for spaces
        encoded_search_term = urllib.parse.quote_plus(search_term)
        expected_search_param = f"search_bar={encoded_search_term}"

        # Assert that it appears 10 times
        self.assertEqual(html_3.count(expected_search_param), 10)

        # for each orderable column, check that 'asc' flips to 'desc', and vice versa
        orderings = (
            "siglum",
            "incipit",
            "service",
            "feast",
            "genre",
            "cantus_id",
            "mode",
            "has_fulltext",
            "has_melody",
            "has_image",
        )
        for ordering in orderings:
            response_asc = self.client.get(
                reverse("chant-search"),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "asc",
                },
            )
            html_asc = str(response_asc.content)
            # the expected substring should be found in the `href` attribute of the `a` tag
            # in the column header in question. Since the results are currently being ordered
            # by that column, sorted ascending, this link should switch the results to being
            # sorted descending.
            expected_substring = f"&order={ordering}&sort=desc"
            self.assertIn(expected_substring, html_asc)
            # when no `sort=` is specified, all 9 columns should contain a `sort=asc` in
            # their column header link. Since an ascending sorting _is_ specified for one
            # of the columns, that column should have switched from `sort=asc` to `sort=desc`
            self.assertEqual(html_asc.count("sort=asc"), 9)
            response_desc = self.client.get(
                reverse("chant-search"),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "desc",
                },
            )
            response_desc = self.client.get(
                reverse("chant-search"),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "desc",
                },
            )
            html_desc = str(response_desc.content)
            # the expected substring should be found in the `href` attribute of the `a` tag
            # in the column header in question. Since the results are currently being ordered
            # by that column, sorted descending, this link should switch the results to being
            # sorted ascending.
            expected_substring = f"&order={ordering}&sort=asc"
            self.assertIn(expected_substring, html_desc)

    def test_source_link_column(self):
        shelfmark = "Sigl-01"
        holding_institution = make_fake_institution(
            name="fake institution", siglum="AA-Bb"
        )
        source = make_fake_source(
            published=True, shelfmark=shelfmark, holding_institution=holding_institution
        )
        url = source.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        _ = make_fake_chant(source=source, manuscript_full_text_std_spelling=fulltext)
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        self.assertContains(
            response,
            f'<a href="{url}" title="{source.heading}">{source.short_heading}</a>',
            html=True,
        )

    def test_folio_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling=fulltext
        )
        folio = chant.folio
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(folio, html)

    def test_feast_column(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast()
        feast_name = feast.name
        feast_description = feast.description
        url = feast.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            feast=feast,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        self.assertContains(
            response,
            f'<a href="{url}" title="{feast_description}">{feast_name}</a>',
            html=True,
        )

    def test_service_column(self):
        source = make_fake_source(published=True)
        service = make_fake_service()
        service_name = service.name
        service_description = service.description
        url = service.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            service=service,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        self.assertContains(
            response,
            f'<a href="{url}" title="{service_description}">{service_name}</a>',
            html=True,
        )

    def test_genre_column(self):
        source = make_fake_source(published=True)
        genre = make_fake_genre()
        genre_name = genre.name
        genre_description = genre.description
        url = genre.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            genre=genre,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        self.assertContains(
            response,
            f'<a href="{url}" title="{genre_description}">{genre_name}</a>',
            html=True,
        )

    def test_position_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        position = chant.position
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(position, html)

    def test_cantus_id_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        cantus_id = chant.cantus_id
        url = chant.get_ci_url()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        self.assertContains(
            response, f'<a href="{url}" target="_blank">{cantus_id}</a>', html=True
        )

    def test_mode_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        mode = "this is the mode"  # not a representative value, but
        # single numerals are found elsewhere in the template
        chant.mode = mode
        chant.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(mode, html)

    def test_manuscript_full_text_column(self):
        source = make_fake_source(published=True)
        std_fulltext = "standard full text"
        ms_fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=std_fulltext,
            manuscript_full_text=ms_fulltext,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(
            "\\xe2\\x9c\\x94",  # checkmark character
            html,
        )
        self.assertInHTML(
            '<span title="Chant record includes Manuscript Full Text">\\xe2\\x9c\\x94</span>',
            html,
        )

        chant.manuscript_full_text = None
        chant.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertNotIn(
            "\\xe2\\x9c\\x94",  # checkmark character
            html,
        )

    def test_volpiano_column(self):
        source = make_fake_source(published=True)
        full_text = "standard full text"
        search_term = "full"
        volpiano = "1---h--j---k--h---m---m---l"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=full_text,
            volpiano=volpiano,
        )
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertIn(
            "\\xe2\\x99\\xab",  # beamed eighth notes character
            html,
        )
        self.assertIn(
            '<span title="Chant record has Volpiano melody">\\xe2\\x99\\xab</span>',
            html,
        )
        chant.volpiano = None
        chant.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        html = str(response.content)
        self.assertNotIn(
            "\\xe2\\x99\\xab",  # beamed eighth notes character
            html,
        )

    def test_image_link_column(self):
        source = make_fake_source(published=True)
        fulltext = "standard full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        image_link = "http://www.example.com/image_link"
        chant.image_link = image_link
        chant.save()
        response = self.client.get(
            reverse("chant-search"), {"keyword": search_term, "op": "contains"}
        )
        self.assertContains(
            response, f'<a href="{image_link}" target="_blank">Image</a>', html=True
        )


class ChantSearchMSViewTest(ChantPermissionsTestCase):
    def test_url_and_templates(self):
        source = make_fake_source()
        response = self.client.get(reverse("chant-search-ms", args=[source.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "chant_search.html")

    def test_permissions(self) -> None:
        published_source = self.chants["published_chant"].source
        self.run_request_permissions_test(
            url=reverse("chant-search-ms", args=[published_source.id]),
            get_allowed_users=[
                "anonymous user",
                "user",
                "editor",
                "superuser",
                "global viewer",
            ],
            post_allowed_users=[],
            test_name="Published source",
        )
        user_assigned_source = self.chants["user_assigned_chant"].source
        self.run_request_permissions_test(
            url=reverse("chant-search-ms", args=[user_assigned_source.id]),
            get_allowed_users=["user", "superuser", "global viewer"],
            post_allowed_users=[],
            test_name="User assigned source",
        )
        editor_assigned_source = self.chants["editor_assigned_chant"].source
        self.run_request_permissions_test(
            url=reverse("chant-search-ms", args=[editor_assigned_source.id]),
            get_allowed_users=["editor", "superuser", "global viewer"],
            post_allowed_users=[],
            test_name="Editor assigned source",
        )
        unassigned_source = self.chants["unassigned_chant"].source
        self.run_request_permissions_test(
            url=reverse("chant-search-ms", args=[unassigned_source.id]),
            get_allowed_users=["superuser", "global viewer"],
            post_allowed_users=[],
            test_name="Unassigned source",
        )

    def test_search_by_service(self):
        source = make_fake_source()
        service = make_fake_service()
        chant = make_fake_chant(source=source, service=service)
        search_term = service.id
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"service": search_term}
        )
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_filter_by_genre(self):
        source = make_fake_source()
        genre = make_fake_genre()
        chant = make_fake_chant(source=source, genre=genre)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"genre": genre.id}
        )
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_cantus_id(self):
        source = make_fake_source()
        chant = make_fake_chant(source=source, cantus_id=faker.numerify("######"))
        search_term = get_random_search_term(chant.cantus_id)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"cantus_id": search_term}
        )
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_mode(self):
        source = make_fake_source()
        chant = make_fake_chant(source=source, mode=faker.numerify("#"))
        search_term = get_random_search_term(chant.mode)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"mode": search_term}
        )
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_feast(self):
        source = make_fake_source()
        feast = make_fake_feast()
        chant = make_fake_chant(source=source, feast=feast)
        search_term = get_random_search_term(feast.name)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"feast": search_term}
        )
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_search_by_position(self):
        source = make_fake_source(published=True)
        position = 1
        chant = make_fake_chant(source=source, position=position)
        search_term = "1"
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"position": search_term}
        )
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant.id, context_chant_id)

    def test_filter_by_melody(self):
        source = make_fake_source()
        chant_with_melody = make_fake_chant(
            source=source,
            volpiano=make_fake_volpiano,
        )
        # Create a chant without melody that won't be in the result
        make_fake_chant(source=source, volpiano=None)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]), {"melodies": "true"}
        )
        # only chants with melodies should be in the result
        self.assertEqual(len(response.context["chants"]), 1)
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(context_chant_id, chant_with_melody.id)

    def test_keyword_search_starts_with(self):
        source = make_fake_source()
        search_term = "quick"

        # We have three chants to make sure the result is only chant 1 where quick is the first word
        chant_1 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="quick brown fox jumps over the lazy dog",
        )
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="brown fox jumps over the lazy dog",
        )
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="lazy brown fox jumps quick over the dog",
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "starts_with"},
        )
        self.assertEqual(len(response.context["chants"]), 1)
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant_1.id, context_chant_id)

    def test_keyword_search_contains(self):
        source = make_fake_source()
        search_term = "quick"
        chant_1 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="Quick brown fox jumps over the lazy dog",
        )
        # Make a chant that won't be returned by the search term
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="brown fox jumps over the lazy dog",
        )
        chant_3 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="lazy brown fox jumps quickly over the dog",
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        first_context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant_1.id, first_context_chant_id)
        second_context_chant_id = response.context["chants"][1].id
        self.assertEqual(chant_3.id, second_context_chant_id)

    def test_indexing_notes_search_starts_with(self):
        source = make_fake_source()
        search_term = "quick"

        # We have three chants to make sure the result is only chant 1 where quick is the first word
        chant_1 = make_fake_chant(
            source=source,
            indexing_notes="quick brown fox jumps over the lazy dog",
        )
        make_fake_chant(
            source=source,
            indexing_notes="brown fox jumps over the lazy dog",
        )
        make_fake_chant(
            source=source,
            indexing_notes="lazy brown fox jumps quick over the dog",
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"indexing_notes": search_term, "indexing_notes_op": "starts_with"},
        )
        self.assertEqual(len(response.context["chants"]), 1)
        context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant_1.id, context_chant_id)

    def test_indexing_notes_search_contains(self):
        source = make_fake_source()
        search_term = "quick"
        chant_1 = make_fake_chant(
            source=source,
            indexing_notes="Quick brown fox jumps over the lazy dog",
        )
        # Make a chant that won't be returned by the search term
        make_fake_chant(
            source=source,
            indexing_notes="brown fox jumps over the lazy dog",
        )
        chant_3 = make_fake_chant(
            source=source,
            indexing_notes="lazy brown fox jumps quickly over the dog",
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"indexing_notes": search_term, "indexing_notes_op": "contains"},
        )
        first_context_chant_id = response.context["chants"][0].id
        self.assertEqual(chant_1.id, first_context_chant_id)
        second_context_chant_id = response.context["chants"][1].id
        self.assertEqual(chant_3.id, second_context_chant_id)

    def test_keyword_search_searching_all_fields(self):
        search_term = "brevity"
        includes_search_term = "brevity is the soul of wit"
        doesnt_include_search_term = "longevity is the soul of wit"
        source = make_fake_source()

        make_fake_chant(
            source=source,
            manuscript_full_text=includes_search_term,  # <== includes_search_term
            manuscript_full_text_std_spelling=doesnt_include_search_term,
        )

        make_fake_chant(
            source=source,
            manuscript_full_text=doesnt_include_search_term,
            manuscript_full_text_std_spelling=includes_search_term,  # <==
        )

        # some chants inherited from OldCantus have an incipit but no full-text -
        # we need to ensure these chants appear in the results
        chant_incipit = make_fake_chant(
            source=source,
        )
        Chant.objects.filter(id=chant_incipit.id).update(
            incipit=includes_search_term,  # <==
            manuscript_full_text=None,
            manuscript_full_text_std_spelling=None,
        )

        # This chant contains no search terms
        make_fake_chant(
            source=source,
            manuscript_full_text=doesnt_include_search_term,
            manuscript_full_text_std_spelling=doesnt_include_search_term,
        )

        response_starts_with = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "starts_with"},
        )
        self.assertEqual(len(response_starts_with.context["chants"]), 3)
        response_contains = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        self.assertEqual(len(response_contains.context["chants"]), 3)

    def test_order_by_incipit(self):
        source = make_fake_source(published=True)
        chant_1 = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="higgledy"
        )
        chant_2 = make_fake_chant(
            source=source, manuscript_full_text_std_spelling="piggledy"
        )

        search_term = "iggl"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "incipit",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "incipit",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_feast(self):
        source = make_fake_source(published=True)
        feast1 = make_fake_feast(name="A")
        feast2 = make_fake_feast(name="B")
        chant_1 = make_fake_chant(source=source, feast=feast1)
        chant_2 = make_fake_chant(source=source, feast=feast2)

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "order": "feast",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_feast = ascending_results[0].feast
        self.assertEqual(first_result_feast, chant_1.feast)
        last_result_feast = ascending_results[1].feast
        self.assertEqual(last_result_feast, chant_2.feast)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "order": "feast",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_feast = descending_results[0].feast
        self.assertEqual(first_result_feast, chant_2.feast)
        last_result_feast = descending_results[1].feast
        self.assertEqual(last_result_feast, chant_1.feast)

    def test_order_by_service(self):
        source = make_fake_source()
        # currently, service sort works by ID rather than by name
        service_1 = make_fake_service(name="A")
        service_2 = make_fake_service(name="B")
        chant_1 = make_fake_chant(
            service=service_1, manuscript_full_text_std_spelling="hocus", source=source
        )
        chant_2 = make_fake_chant(
            service=service_2, manuscript_full_text_std_spelling="pocus", source=source
        )

        search_term = "ocu"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "service",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "service",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_genre(self):
        source = make_fake_source()
        # currently, genre sort works by ID rather than by name
        genre_1 = make_fake_genre(name="A")
        genre_2 = make_fake_genre(name="B")
        assert genre_1.id < genre_2.id
        chant_1 = make_fake_chant(
            genre=genre_1, manuscript_full_text_std_spelling="hocus", source=source
        )
        chant_2 = make_fake_chant(
            genre=genre_2, manuscript_full_text_std_spelling="pocus", source=source
        )

        search_term = "ocu"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "genre",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "genre",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_cantus_id(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="isaac", cantus_id="121393", source=source
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="baal", cantus_id="196418", source=source
        )

        search_term = "aa"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "cantus_id",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "cantus_id",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_mode(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="For thirdly he works it upon stretch with the forepaws extended",
            mode="1",
            source=source,
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="For fourthly he sharpens his paws by wood",
            mode="2",
            source=source,
        )

        search_term = "for"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "mode",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "mode",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_ms_fulltext(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant with a MS spelling fulltext",
            manuscript_full_text="this is a chant with a MS spelling fylltexte",
            source=source,
        )
        chant_2 = make_fake_chant(
            manuscript_full_text_std_spelling="this is a chant without",
            source=source,
        )
        chant_2.manuscript_full_text = ""
        chant_2.save()

        search_term = "s is a ch"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_fulltext",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_fulltext",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_volpiano(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="this is a chant with volpiano",
            volpiano="1---d---d---a--a---a---e--f--e---d---4",
        )
        chant_2 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="this is a chant about parsley",
        )
        chant_2.volpiano = ""
        chant_2.save()

        search_term = "s is a ch"

        response_ascending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_melody",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_melody",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_by_image_link(self):
        source = make_fake_source()
        chant_1 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="this is a chant with a link",
            image_link="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        )
        chant_2 = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling="this is a chant without",
        )
        chant_2.image_link = ""
        chant_2.save()

        search_term = "a chant with"

        response_ascending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_image",
                "sort": "asc",
            },
        )
        ascending_results = response_ascending.context["chants"]
        first_result_incipit = ascending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_1.incipit)
        last_result_incipit = ascending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_2.incipit)

        response_descending = self.client.get(
            reverse("chant-search"),
            {
                "keyword": search_term,
                "op": "contains",
                "order": "has_image",
                "sort": "desc",
            },
        )
        descending_results = response_descending.context["chants"]
        first_result_incipit = descending_results[0].incipit
        self.assertEqual(first_result_incipit, chant_2.incipit)
        last_result_incipit = descending_results[1].incipit
        self.assertEqual(last_result_incipit, chant_1.incipit)

    def test_order_nulls_last(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast(name="A")

        chant_with_feast = make_fake_chant(source=source, feast=feast)
        chant_without_feast = make_fake_chant(source=source, feast=None)

        # Ascending sort — null should be last
        response_asc = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "order": "feast",
                "sort": "asc",
            },
        )
        ascending_results = response_asc.context["chants"]
        self.assertIn(chant_with_feast, ascending_results)
        self.assertIn(chant_without_feast, ascending_results)

        self.assertEqual(ascending_results[0].feast, feast)
        self.assertIsNone(ascending_results[1].feast)

        # Descending sort — null should still be last
        response_desc = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "order": "feast",
                "sort": "desc",
            },
        )
        descending_results = response_desc.context["chants"]
        self.assertEqual(descending_results[0].feast, feast)
        self.assertIsNone(descending_results[1].feast)

    def test_column_header_links(self):
        # these are the 9 column headers users can order by:
        shelfmark = "glum-01"
        full_text = "this is a full text that begins with the search term"
        search_term = "this is a fu"
        service = make_fake_service()
        genre = make_fake_genre()
        cantus_id = make_random_string(6, "0123456789")
        mode = make_random_string(1, "0123456789*?")
        mel = make_fake_volpiano()
        image = faker.image_url()

        source = make_fake_source(shelfmark=shelfmark, published=True)

        # additional properties for which there are search fields
        feast = make_fake_feast()
        position = make_random_string(1)
        make_fake_chant(
            service=service,
            genre=genre,
            cantus_id=cantus_id,
            mode=mode,
            manuscript_full_text_std_spelling=full_text,
            volpiano=mel,
            image_link=image,
            source=source,
            feast=feast,
            position=position,
        )
        response_1 = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {
                "keyword": search_term,
            },
        )
        html_1 = str(response_1.content)
        # if no ordering specified, all 9 links should include "&sort=asc"
        self.assertEqual(html_1.count("&sort=asc"), 9)

        # test that all query parameters are present in all 9 links
        query_keys_and_values = {
            "op": "contains",
            "keyword": search_term,
            "service": service.id,
            "genre": genre.id,
            "cantus_id": cantus_id,
            "mode": mode,
            "feast": feast.name,
            "position": position,
            "melodies": "true",
        }
        response_2 = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            query_keys_and_values,
        )
        html_2 = str(response_2.content)

        for k, v in query_keys_and_values.items():
            # Generate URL-encoded parameter with + for spaces (how Django's urlencode works)
            v_str = str(v)
            encoded_param = urllib.parse.quote_plus(v_str)
            expected_query_param = f"{k}={encoded_param}"

            # Assert that it appears 10 times
            self.assertEqual(html_2.count(expected_query_param), 9)
            self.assertEqual(html_2.count("sort=asc"), 9)

        # for each orderable column, check that 'asc' flips to 'desc', and vice versa
        orderings = (
            "incipit",
            "service",
            "genre",
            "cantus_id",
            "mode",
            "has_fulltext",
            "has_melody",
            "has_image",
        )
        for ordering in orderings:
            response_asc = self.client.get(
                reverse("chant-search-ms", args=[source.id]),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "asc",
                },
            )
            html_asc = str(response_asc.content)
            # the expected substring should be found in the `href` attribute of the `a` tag
            # in the column header in question. Since the results are currently being ordered
            # by that column, sorted ascending, this link should switch the results to being
            # sorted descending.
            expected_substring = f"&order={ordering}&sort=desc"
            self.assertIn(expected_substring, html_asc)
            # when no `sort=` is specified, all 7 columns should contain a `sort=asc` in
            # their column header link. Since an ascending sorting _is_ specified for one
            # of the columns, that column should have switched from `sort=asc` to `sort=desc`
            self.assertEqual(html_asc.count("sort=asc"), 8)
            response_desc = self.client.get(
                reverse("chant-search-ms", args=[source.id]),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "desc",
                },
            )
            response_desc = self.client.get(
                reverse("chant-search-ms", args=[source.id]),
                {
                    "search_bar": search_term,
                    "order": ordering,
                    "sort": "desc",
                },
            )
            html_desc = str(response_desc.content)
            # the expected substring should be found in the `href` attribute of the `a` tag
            # in the column header in question. Since the results are currently being ordered
            # by that column, sorted descending, this link should switch the results to being
            # sorted ascending.
            expected_substring = f"&order={ordering}&sort=asc"
            self.assertIn(expected_substring, html_desc)

    def test_source_link_column(self):
        shelfmark = "Sigl-01"
        source = make_fake_source(published=True, shelfmark=shelfmark)
        source_shelfmark = source.shelfmark
        url = source.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        make_fake_chant(source=source, manuscript_full_text_std_spelling=fulltext)
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(shelfmark, html)
        self.assertIn(source_shelfmark, html)
        self.assertIn(url, html)
        self.assertIn(
            f'<a href="{url}" target="_blank">{source.short_heading}</a>', html
        )

    def test_folio_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source, manuscript_full_text_std_spelling=fulltext
        )
        folio = chant.folio
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(folio, html)

    def test_feast_column(self):
        source = make_fake_source(published=True)
        feast = make_fake_feast()
        feast_name = feast.name
        feast_description = feast.description
        url = feast.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            feast=feast,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        self.assertContains(
            response,
            f'<a href="{url}" title="{feast_description}">{feast_name}</a>',
            html=True,
        )

    def test_service_column(self):
        source = make_fake_source(published=True)
        service = make_fake_service()
        service_name = service.name
        service_description = service.description
        url = service.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            service=service,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        self.assertContains(
            response,
            f'<a href="{url}" title="{service_description}">{service_name}</a>',
            html=True,
        )

    def test_genre_column(self):
        source = make_fake_source(published=True)
        genre = make_fake_genre()
        genre_name = genre.name
        genre_description = genre.description
        url = genre.get_absolute_url()
        fulltext = "manuscript full text"
        search_term = "full"
        make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
            genre=genre,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        self.assertContains(
            response,
            f'<a href="{url}" title="{genre_description}">{genre_name}</a>',
            html=True,
        )

    def test_position_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        position = chant.position
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(position, html)

    def test_cantus_id_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        cantus_id = chant.cantus_id
        url = chant.get_ci_url()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        self.assertContains(
            response, f'<a href="{url}" target="_blank">{cantus_id}</a>', html=True
        )

    def test_mode_column(self):
        source = make_fake_source(published=True)
        fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        mode = "this is the mode"  # not a representative value, but
        # single numerals are found elsewhere in the template
        chant.mode = mode
        chant.save()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(mode, html)

    def test_manuscript_full_text_column(self):
        source = make_fake_source(published=True)
        std_fulltext = "standard full text"
        ms_fulltext = "manuscript full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=std_fulltext,
            manuscript_full_text=ms_fulltext,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(
            "\\xe2\\x9c\\x94",  # checkmark character
            html,
        )
        self.assertIn(
            '<span title="Chant record includes Manuscript Full Text">\\xe2\\x9c\\x94</span>',
            html,
        )

        chant.manuscript_full_text = None
        chant.save()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertNotIn(
            "\\xe2\\x9c\\x94",  # checkmark character
            html,
        )

    def test_volpiano_column(self):
        source = make_fake_source(published=True)
        full_text = "standard full text"
        search_term = "full"
        volpiano = "1---defg-e-cd"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=full_text,
            volpiano=volpiano,
        )
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(
            "\\xe2\\x99\\xab",  # beamed eighth notes character
            html,
        )
        self.assertIn(
            '<span title="Chant record has Volpiano melody">\\xe2\\x99\\xab</span>',
            html,
        )
        chant.volpiano = None
        chant.save()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertNotIn(
            "\\xe2\\x99\\xab",  # beamed eighth notes character
            html,
        )

    def test_image_link_column(self):
        source = make_fake_source(published=True)
        fulltext = "standard full text"
        search_term = "full"
        chant = make_fake_chant(
            source=source,
            manuscript_full_text_std_spelling=fulltext,
        )
        image_link = "http://www.example.com/image_link"
        chant.image_link = image_link
        chant.save()
        response = self.client.get(
            reverse("chant-search-ms", args=[source.id]),
            {"keyword": search_term, "op": "contains"},
        )
        html = str(response.content)
        self.assertIn(image_link, html)
        self.assertIn(f'<a href="{image_link}" target="_blank">Image</a>', html)


@patch("requests.get", mock_requests_get)
class ChantCreateViewTest(CustomAccessTestMixin, TestCase):
    source: ClassVar[Source]
    default_user = "user"

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.source = make_fake_source()
        cls.source.current_editors.add(cls.users["user"])
        cls.source.save()

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse("chant-create", args=[self.source.id]),
            get_allowed_users=["user", "superuser"],
            post_allowed_users=["user", "superuser"],
            test_name="User assigned source",
        )
        editor_assigned_source = make_fake_source()
        editor_assigned_source.current_editors.add(self.users["editor"])
        editor_assigned_source.save()
        self.run_request_permissions_test(
            url=reverse("chant-create", args=[editor_assigned_source.id]),
            get_allowed_users=["editor", "superuser"],
            post_allowed_users=["editor", "superuser"],
            test_name="Editor assigned source",
        )

    def test_url_and_templates(self) -> None:
        source = self.source
        response_1 = self.client.get(reverse("chant-create", args=[source.id]))

        self.assertEqual(response_1.status_code, 200)
        self.assertTemplateUsed(response_1, "chant_create.html")
        self.assertTemplateUsed(response_1, "base.html")

    def test_create_chant(self) -> None:
        source = self.source
        response = self.client.post(
            reverse("chant-create", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "initial",
                "folio": "001r",
                "c_sequence": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse("chant-create", args=[source.id]))
        chant = Chant.objects.get(source=source)
        self.assertEqual(chant.manuscript_full_text_std_spelling, "initial")

    def test_view_url_path(self) -> None:
        source = self.source
        response = self.client.get(f"/chant-create/{source.id}")
        self.assertEqual(response.status_code, 200)

    def test_context(self) -> None:
        """Test that correct source is in context"""
        source = self.source
        url = reverse("chant-create", args=[source.id])
        response = self.client.get(url)
        self.assertEqual(response.context["source"].id, source.id)

    def test_empty_fulltext(self) -> None:
        """post with correct source and empty full-text"""
        source = self.source
        url = reverse("chant-create", args=[source.id])
        response = self.client.post(
            url,
            data={
                "manuscript_full_text_std_spelling": "",
                "folio": "010r",
                "c_sequence": "1",
            },
        )

        self.assertFormError(
            response.context["form"],
            "manuscript_full_text_std_spelling",
            "This field is required.",
        )

    def test_nonexistent_source(self) -> None:
        """
        users should not be able to access Chant Create page for a source that doesn't exist
        """
        nonexistent_source_id = faker.numerify(
            "#####"
        )  # there's not supposed to be 5-digits source id
        with patch("requests.get", mock_requests_get):
            response = self.client.get(
                reverse("chant-create", args=[nonexistent_source_id])
            )
        self.assertEqual(response.status_code, 404)

    def test_repeated_seq(self) -> None:
        """post with a folio and seq that already exists in the source"""
        test_folio = "001r"
        # create some chants in the test source
        source = self.source
        for i in range(1, 5):
            make_fake_chant(
                source=source,
                manuscript_full_text=" ".join(faker.words(faker.random_int(3, 10))),
                folio=test_folio,
                c_sequence=i,
            )
        # post a chant with the same folio and seq
        url = reverse("chant-create", args=[source.id])
        fake_text = "this is also a fake but valid text"
        response = self.client.post(
            url,
            data={
                "manuscript_full_text_std_spelling": fake_text,
                "folio": test_folio,
                "c_sequence": random.randint(1, 4),
            },
            follow=True,
        )
        self.assertFormError(
            response.context["form"],
            None,
            errors="Chant with the same sequence and folio already exists in this source.",
        )

    def test_volpiano_signal(self) -> None:
        source = self.source
        self.client.post(
            reverse("chant-create", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "ut queant lactose",
                "folio": "001r",
                "c_sequence": "1",
                # liquescents, to be converted to lowercase
                #                    vv v v v v v v
                "volpiano": "9abcdefg)A-B1C2D3E4F5G67?. yiz",
                #                      ^ ^ ^ ^ ^ ^ ^^^^^^^^
                # clefs, accidentals, etc., to be deleted
            },
        )
        chant_1 = Chant.objects.get(
            manuscript_full_text_std_spelling="ut queant lactose"
        )
        self.assertEqual(chant_1.volpiano, "9abcdefg)A-B1C2D3E4F5G67?. yiz")
        self.assertEqual(chant_1.volpiano_notes, "9abcdefg9abcdefg")
        self.client.post(
            reverse("chant-create", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "resonare foobaz",
                "folio": "001r",
                "c_sequence": "2",
                "volpiano": "abacadaeafagahaja",
            },
        )
        chant_2 = Chant.objects.get(manuscript_full_text_std_spelling="resonare foobaz")
        self.assertEqual(chant_2.volpiano, "abacadaeafagahaja")
        self.assertEqual(chant_2.volpiano_intervals, "1-12-23-34-45-56-67-78-8")

    def test_initial_values(self) -> None:
        # create a chant with a known folio, feast, service, c_sequence and image_link
        source: Source = self.source
        folio: str = "001r"
        sequence: int = 1
        feast: Feast = make_fake_feast()
        service: Service = make_fake_service()
        image_link: str = "https://www.youtube.com/watch?v=9bZkp7q19f0"
        self.client.post(
            reverse("chant-create", args=[source.id]),
            {
                "manuscript_full_text_std_spelling": "this is a bog standard manuscript textful spelling",
                "folio": folio,
                "c_sequence": str(sequence),
                "feast": feast.id,
                "service": service.id,
                "image_link": image_link,
            },
        )
        # when we request the Chant Create page, the same folio, feast, service and image_link should
        # be preselected, and c_sequence should be incremented by 1.
        response = self.client.get(
            reverse("chant-create", args=[source.id]),
        )

        observed_initial_folio: int = response.context["form"].initial["folio"]
        with self.subTest(subtest="test initial value of folio field"):
            self.assertEqual(observed_initial_folio, folio)

        observed_initial_feast: int = response.context["form"].initial["feast"]
        with self.subTest(subtest="test initial value of feast feild"):
            self.assertEqual(observed_initial_feast, feast.id)

        observed_initial_service: int = response.context["form"].initial["service"]
        with self.subTest(subtest="test initial value of service field"):
            self.assertEqual(observed_initial_service, service.id)

        observed_initial_sequence: int = response.context["form"].initial["c_sequence"]
        with self.subTest(subtest="test initial value of c_sequence field"):
            self.assertEqual(observed_initial_sequence, sequence + 1)

        observed_initial_image: int = response.context["form"].initial["image_link"]
        with self.subTest(subtest="test initial value of image_link field"):
            self.assertEqual(observed_initial_image, image_link)

    def test_suggested_chant_buttons(self) -> None:
        source: Source = self.source
        response_empty_source = self.client.get(
            reverse("chant-create", args=[source.id]),
        )
        with self.subTest(
            test="Ensure no suggestions displayed when there is no previous chant"
        ):
            self.assertNotContains(
                response_empty_source, "Suggestions based on previous chant:"
            )

        # Make a chant to serve as the previous chant
        make_fake_chant(cantus_id="001010", source=source)
        response_after_previous_chant = self.client.get(
            reverse("chant-create", args=[source.id]),
        )
        suggested_chants = response_after_previous_chant.context["suggested_chants"]
        with self.subTest(
            test="Ensure suggested chant suggestions present when previous chant exists"
        ):
            self.assertContains(
                response_after_previous_chant, "Suggestions based on previous chant:"
            )
            self.assertIsNotNone(suggested_chants)
            self.assertEqual(len(suggested_chants), 5)

        # Make a chant with a rare cantus_id to serve as the previous chant
        make_fake_chant(cantus_id="a07763", source=source)
        response_after_rare_chant = self.client.get(
            reverse("chant-create", args=[source.id]),
        )
        with self.subTest(
            test="When previous chant has no suggested chants, ensure no suggestions are displayed"
        ):
            self.assertContains(
                response_after_rare_chant, "Suggestions based on previous chant:"
            )
            self.assertContains(
                response_after_rare_chant, "Sorry! No suggestions found."
            )
            self.assertIsNone(response_after_rare_chant.context["suggested_chants"])

    @skip("Temporarily disabled due to #1674")
    def test_invalid_text(self) -> None:
        """
        The user should not be able to create a chant with invalid text
        (either invalid characters or unmatched brackets).
        Instead, the user should be shown an error message.
        """
        with self.subTest("Chant with invalid characters"):
            source = self.source
            response = self.client.post(
                reverse("chant-create", args=[source.id]),
                {
                    "manuscript_full_text_std_spelling": "this is a ch@nt t%xt with inv&lid ch!ra+ers",
                    "folio": "001r",
                    "c_sequence": "1",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertFormError(
                response.context["form"],
                "manuscript_full_text_std_spelling",
                "Invalid characters in text.",
            )
        with self.subTest("Chant with unmatched brackets"):
            source = self.source
            response = self.client.post(
                reverse("chant-create", args=[source.id]),
                {
                    "manuscript_full_text_std_spelling": "this is a chant with [ unmatched brackets",
                    "folio": "001r",
                    "c_sequence": "1",
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertFormError(
                response.context["form"],
                "manuscript_full_text_std_spelling",
                "Word [ contains non-alphabetic characters.",
            )


class CISearchViewTest(TestCase):

    def test_valid_search_term(self):
        with patch("requests.get", mock_requests_get):
            response = self.client.get(reverse("ci-search", args=["qui est"]))

        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertIn("results", context)
        self.assertFalse(context["ci_error"])

        results_zip = context["results"]

        self.assertEqual(len(results_zip), 50)
        first_result = results_zip[0]
        self.assertEqual(first_result[0], "001774")
        self.assertEqual(
            first_result[2],
            "Caro et sanguis non revelavit tibi sed pater meus qui est in caelis",
        )

        second_result = results_zip[1]
        self.assertEqual(second_result[0], "002191")
        self.assertEqual(
            second_result[2],
            "Dicebat Jesus turbis Judaeorum et principibus sacerdotum qui est ex deo verba dei audit responderunt Judaei et dixerunt ei nonne bene dicimus nos quia Samaritanus es tu et daemonium habes respondit Jesus ego daemonium non habeo sed honorifico patrem meum et vos inhonorastis me",
        )

    def test_invalid_search_term(self):
        with patch("requests.get", mock_requests_get):
            response = self.client.get(reverse("ci-search", args=["123xyz"]))

        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertTrue(context["ci_error"])
        self.assertEqual(list(context["results"]), [])

    def test_server_error(self):
        with patch("requests.get", mock_requests_get):
            response = self.client.get(reverse("ci-search", args=["server_error"]))

        self.assertEqual(response.status_code, 200)
        context = response.context
        self.assertTrue(context["ci_error"])
        self.assertEqual(list(context["results"]), [])


class ChantDeleteViewTest(ChantPermissionsTestCase):
    default_user = "superuser"

    def test_context(self):
        chant = make_fake_chant()
        response = self.client.get(reverse("chant-delete", args=[chant.id]))
        self.assertEqual(chant, response.context["object"])

    def test_url_and_templates(self):
        chant = make_fake_chant()

        response = self.client.get(reverse("chant-delete", args=[chant.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "chant_delete.html")

        response = self.client.get(reverse("chant-delete", args=[chant.id + 100]))
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")

    def test_existing_chant(self):
        chant = make_fake_chant()
        response = self.client.post(reverse("chant-delete", args=[chant.id]))
        self.assertEqual(response.status_code, 302)

    def test_non_existing_chant(self):
        chant = make_fake_chant()
        response = self.client.post(reverse("chant-delete", args=[chant.id + 100]))
        self.assertEqual(response.status_code, 404)

    def test_permissions(self) -> None:
        self.run_request_permissions_test(
            url=reverse("chant-delete", args=[self.chants["unassigned_chant"].id]),
            get_allowed_users=["superuser"],
            post_allowed_users=["superuser"],
            test_name="Chant in unassigned source",
        )
        self.run_request_permissions_test(
            url=reverse("chant-delete", args=[self.chants["user_assigned_chant"].id]),
            get_allowed_users=["user", "superuser"],
            post_allowed_users=["user", "superuser"],
            test_name="Chant in user assigned source",
        )
        self.run_request_permissions_test(
            url=reverse("chant-delete", args=[self.chants["editor_assigned_chant"].id]),
            get_allowed_users=["editor", "superuser"],
            post_allowed_users=["editor", "superuser"],
            test_name="Chant in editor assigned source",
        )


class ChantViewHelpersTest(TestCase):
    """
    Tests for the helper functions defined in views.chant
    """

    @classmethod
    def setUpTestData(cls):
        cls.feasts = [make_fake_feast() for _ in range(4)]

    def test_get_feast_selector_options(self) -> None:
        with self.subTest("r/v foliation"):
            source = make_fake_source()
            feasts = self.feasts
            # Create chants for feasts[0] for range 001v, A001v
            for folio in ["A001v", "001v"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[0])
            # Create chants for feasts[1] for range 001r, 002r
            for folio in ["001r", "002r"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[1])
            # Create chants for feasts[2] for range 002r-002v, 003v
            for folio in ["002r", "002v", "003v"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[2])
            # Create a chant on 003r with no feast that should show up in no ranges
            make_fake_chant(source=source, folio="003r", feast=None)
            feast_selector_options = get_feast_selector_options(source)
            expected_result = [
                (feasts[1].id, feasts[1].name, "001r, 002r"),
                (feasts[0].id, feasts[0].name, "001v, A001v"),
                (feasts[2].id, feasts[2].name, "002r-002v, 003v"),
            ]
            self.assertEqual(feast_selector_options, expected_result)
        with self.subTest("Foliation with numbers only"):
            source = make_fake_source()
            feasts = self.feasts
            # Create chants for feasts[0] for range 002-004
            for folio in ["002", "003", "004"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[0])
            # Create chants for feasts[1] for range 001, 003
            for folio in ["001", "003"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[1])
            feast_selector_options = get_feast_selector_options(source)
            expected_result = [
                (feasts[1].id, feasts[1].name, "001, 003"),
                (feasts[0].id, feasts[0].name, "002-004"),
            ]
            self.assertEqual(feast_selector_options, expected_result)
        with self.subTest("Unnumbered folios"):
            source = make_fake_source()
            feasts = self.feasts
            # Create chants for feasts[0] for folios 003v-003w, 004v
            for folio in ["003v", "003w", "004v"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[0])
            # Create chants for feasts[1] for folios 002r-002x
            for folio in ["002r", "002x"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[1])
            # Create chants for feasts[2] for folios 003w-004r
            for folio in ["003w", "004r"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[2])
            # Create chants for feasts[3] for folios 003w-003x
            for folio in ["003x", "003w"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[3])
            feast_selector_options = get_feast_selector_options(source)
            expected_result = [
                (feasts[1].id, feasts[1].name, "002r-002x"),
                (feasts[0].id, feasts[0].name, "003v-003w, 004v"),
                (feasts[3].id, feasts[3].name, "003w-003x"),
                (feasts[2].id, feasts[2].name, "003w-004r"),
            ]
            self.assertEqual(feast_selector_options, expected_result)
        with self.subTest("Unexpected folio numbers"):
            # This subTest ensures that unexpected folio numbers (say,
            # a something like "00q1r") are added correctly to ranges.
            source = make_fake_source()
            feasts = self.feasts
            # Create chants for feasts[0] with a normal range (001r-002r)
            for folio in ["001r", "001v", "002r"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[0])
            # Create chants for feasts[1] with an unexpected folio number (00q1r)
            # and expected folio numbers
            for folio in ["00q1r", "002v", "003r"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[1])
            # Create chants for feasts[2] with only unexpected folio numbers
            for folio in ["00q2r", "00q3", "X00q3"]:
                make_fake_chant(source=source, folio=folio, feast=feasts[2])
            feast_selector_options = get_feast_selector_options(source)
            expected_result = [
                (feasts[0].id, feasts[0].name, "001r-002r"),
                (feasts[1].id, feasts[1].name, "002v-003r, 00q1r"),
                (feasts[2].id, feasts[2].name, "00q2r, 00q3, X00q3"),
            ]
            self.assertEqual(feast_selector_options, expected_result)
