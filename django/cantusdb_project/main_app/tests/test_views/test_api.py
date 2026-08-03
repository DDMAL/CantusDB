"""
Tests for views in views/api.py
"""

import json
import re
from typing import Optional, Any
import csv
from collections.abc import ItemsView, KeysView
from unittest.mock import patch, MagicMock
from urllib.parse import unquote

from django.test import TestCase
from django.urls import reverse
from django.http import HttpResponse, JsonResponse

from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_institution,
    make_fake_sequence,
    make_fake_source,
    make_fake_notation,
    make_fake_provenance,
    make_fake_segment,
    faker,
    get_different_digit,
)
from main_app.models import Chant, Source, Provenance, Notation

from main_app.tests.mock_cantusindex_data import (
    mock_json_cid_008349_json,
    mock_json_cid_006928_json,
)
from main_app.tests.mixins import CustomAccessTestMixin
from main_app.tests.test_views.test_chant import ChantPermissionsTestCase


class AjaxSearchBarTest(ChantPermissionsTestCase):
    def test_response(self):
        chant = make_fake_chant()
        cantus_id = chant.cantus_id

        response = self.client.get(reverse("ajax-search-bar", args=[cantus_id]))
        self.assertEqual(response.status_code, 200)

        content = json.loads(response.content)
        self.assertIsInstance(content, dict)

        content_chants = content["chants"]
        self.assertIsInstance(content_chants, list)

        content_chant = content_chants[0]
        expected_keys_and_values = {
            "incipit": chant.incipit,
            "genre__name": chant.genre.name,
            "feast__name": chant.feast.name,
            "cantus_id": chant.cantus_id,
            "mode": chant.mode,
            "source__shelfmark": chant.source.shelfmark,
            "folio": chant.folio,
            "c_sequence": chant.c_sequence,
            "chant_link": reverse("chant-detail", args=[chant.id]),
        }
        for key, expected_value in expected_keys_and_values.items():
            with self.subTest(key=key):
                observed_value = content_chant[key]
                self.assertEqual(expected_value, observed_value)

    def test_incipit_search(self):
        unremarkable_chant = make_fake_chant(
            manuscript_full_text_std_spelling=(
                "The fulltext contains no "
                "numbers no asterisks and no punctuation "
                "and is thus completely normal"
            )
        )
        chant_with_asterisk = make_fake_chant(
            manuscript_full_text_std_spelling="few words*"
        )

        istartswith_search_term = "the fulltext"
        istartswith_response = self.client.get(
            reverse("ajax-search-bar", args=[istartswith_search_term])
        )
        istartswith_content = json.loads(istartswith_response.content)
        istartswith_chants = istartswith_content["chants"]
        self.assertEqual(len(istartswith_chants), 1)
        istartswith_chant = istartswith_chants[0]
        self.assertEqual(istartswith_chant["id"], unremarkable_chant.id)

        # we should only find chants that begin with the search term
        icontains_search_term = "contains no"
        icontains_response = self.client.get(
            reverse("ajax-search-bar", args=[icontains_search_term])
        )
        icontains_content = json.loads(icontains_response.content)
        icontains_chants = icontains_content["chants"]
        self.assertEqual(len(icontains_chants), 0)

        # the search bar should only switch to a Cantus ID search when
        # there are numerals present. Special characters like asterisks
        # may occur in chant texts, and should still be treated as
        # incipit searches
        asterisk_search_term = "few words*"
        asterisk_response = self.client.get(
            reverse("ajax-search-bar", args=[asterisk_search_term])
        )
        asterisk_content = json.loads(asterisk_response.content)
        asterisk_chants = asterisk_content["chants"]
        self.assertEqual(len(asterisk_chants), 1)
        asterisk_chant = asterisk_chants[0]
        self.assertEqual(asterisk_chant["id"], chant_with_asterisk.id)

    def test_cantus_id_search(self):
        chant_with_normal_cantus_id = self.chants["published_chant"]
        cid_first_dig = int(chant_with_normal_cantus_id.cantus_id[0])
        new_first_dig = get_different_digit(cid_first_dig)
        new_cid = f'{new_first_dig}{faker.numerify("#####")}'
        chant_with_numerals_in_incipit = make_fake_chant(
            cantus_id=new_cid,
            manuscript_full_text_std_spelling=f"{cid_first_dig} me! {cid_first_dig} my! This is unexpected!",
        )

        # for search terms that contain numerals, we should only return
        # matches with the cantus_id field, and not the incipit field
        matching_search_term = cid_first_dig
        matching_response = self.client.get(
            reverse("ajax-search-bar", args=[matching_search_term])
        )
        matching_content = json.loads(matching_response.content)
        matching_chants = matching_content["chants"]
        self.assertEqual(len(matching_chants), 1)
        matching_chant = matching_chants[0]
        matching_id = matching_chant["id"]
        self.assertEqual(matching_id, chant_with_normal_cantus_id.id)
        self.assertNotEqual(matching_id, chant_with_numerals_in_incipit.id)

        # we should only return istartswith results, and not icontains results
        non_matching_search_term = get_different_digit(cid_first_dig, new_first_dig)
        non_matching_response = self.client.get(
            reverse("ajax-search-bar", args=[non_matching_search_term])
        )
        non_matching_content = json.loads(non_matching_response.content)
        non_matching_chants = non_matching_content["chants"]
        self.assertEqual(len(non_matching_chants), 0)

    def test_permissions(self) -> None:
        # All chants in self.chants have the same Cantus ID
        cantus_id = self.chants["published_chant"].cantus_id
        all_chant_ids = [x.id for x in self.chants.values()]
        with self.subTest("Superuser"):
            self.client.force_login(self.users["superuser"])
            response = self.client.get(reverse("ajax-search-bar", args=[cantus_id]))
            returned_chants = json.loads(response.content)["chants"]
            returned_ids = [x["id"] for x in returned_chants]
            self.assertCountEqual(all_chant_ids, returned_ids)
        with self.subTest("Global viewer"):
            self.client.force_login(self.users["global viewer"])
            response = self.client.get(reverse("ajax-search-bar", args=[cantus_id]))
            returned_chants = json.loads(response.content)["chants"]
            returned_ids = [x["id"] for x in returned_chants]
            self.assertCountEqual(all_chant_ids, returned_ids)
        with self.subTest("Editor"):
            self.client.force_login(self.users["editor"])
            response = self.client.get(reverse("ajax-search-bar", args=[cantus_id]))
            returned_chants = json.loads(response.content)["chants"]
            returned_ids = [x["id"] for x in returned_chants]
            self.assertCountEqual(
                [
                    self.chants["published_chant"].id,
                    self.chants["editor_assigned_chant"].id,
                ],
                returned_ids,
            )
        with self.subTest("User"):
            self.client.force_login(self.users["user"])
            response = self.client.get(reverse("ajax-search-bar", args=[cantus_id]))
            returned_chants = json.loads(response.content)["chants"]
            returned_ids = [x["id"] for x in returned_chants]
            self.assertCountEqual(
                [
                    self.chants["published_chant"].id,
                    self.chants["user_assigned_chant"].id,
                ],
                returned_ids,
            )
        with self.subTest("Anonymous User"):
            self.client.logout()
            response = self.client.get(reverse("ajax-search-bar", args=[cantus_id]))
            returned_chants = json.loads(response.content)["chants"]
            returned_ids = [x["id"] for x in returned_chants]
            self.assertCountEqual([self.chants["published_chant"].id], returned_ids)


class AjaxMelodyViewTest(ChantPermissionsTestCase):
    def test_response(self):
        cantus_id: str = "123456"
        number_of_chants: int = 7
        for _ in range(number_of_chants):
            make_fake_chant(cantus_id=cantus_id)

        with self.subTest(subtest="ensure 200 response"):
            response: JsonResponse = self.client.get(
                reverse("ajax-melody", args=[cantus_id])
            )
            self.assertEqual(response.status_code, 200)

        with self.subTest(
            subtest="ensure response unpacks to a dictionary with two items"
        ):
            content: Optional[dict] = json.loads(response.content)
            self.assertIsInstance(content, dict)
            items: ItemsView = content.items()
            self.assertEqual(len(items), 2)

        expected_keys: tuple = (
            "concordances",
            "concordance_count",
        )
        observed_keys: KeysView = content.keys()
        for key in expected_keys:
            with self.subTest(key=key):
                self.assertIn(key, observed_keys)

        with self.subTest(subtest="ensure response['concordances'] is a list"):
            concordances: Optional[list] = content["concordances"]
            self.assertIsInstance(concordances, list)

        with self.subTest(
            subtest="verify type and value of response['concordance_count']"
        ):
            concordance_count: Optional[int] = content["concordance_count"]
            self.assertIsInstance(concordance_count, int)
            self.assertEqual(concordance_count, number_of_chants)

    def test_permissions(self) -> None:
        # All chants in self.chants have the same Cantus ID
        cantus_id = self.chants["published_chant"].cantus_id
        all_chant_ids = [x.get_absolute_url() for x in self.chants.values()]
        with self.subTest("Superuser"):
            self.client.force_login(self.users["superuser"])
            response = self.client.get(reverse("ajax-melody", args=[cantus_id]))
            returned_chants = json.loads(response.content)["concordances"]
            returned_urls = [x["chant_link"] for x in returned_chants]
            self.assertCountEqual(all_chant_ids, returned_urls)
        with self.subTest("Global viewer"):
            self.client.force_login(self.users["global viewer"])
            response = self.client.get(reverse("ajax-melody", args=[cantus_id]))
            returned_chants = json.loads(response.content)["concordances"]
            returned_urls = [x["chant_link"] for x in returned_chants]
            self.assertCountEqual(all_chant_ids, returned_urls)
        with self.subTest("Editor"):
            self.client.force_login(self.users["editor"])
            response = self.client.get(reverse("ajax-melody", args=[cantus_id]))
            returned_chants = json.loads(response.content)["concordances"]
            returned_urls = [x["chant_link"] for x in returned_chants]
            self.assertCountEqual(
                [
                    self.chants["published_chant"].get_absolute_url(),
                    self.chants["editor_assigned_chant"].get_absolute_url(),
                ],
                returned_urls,
            )
        with self.subTest("User"):
            self.client.force_login(self.users["user"])
            response = self.client.get(reverse("ajax-melody", args=[cantus_id]))
            returned_chants = json.loads(response.content)["concordances"]
            returned_urls = [x["chant_link"] for x in returned_chants]
            self.assertCountEqual(
                [
                    self.chants["published_chant"].get_absolute_url(),
                    self.chants["user_assigned_chant"].get_absolute_url(),
                ],
                returned_urls,
            )
        with self.subTest("Anonymous User"):
            self.client.logout()
            response = self.client.get(reverse("ajax-melody", args=[cantus_id]))
            returned_chants = json.loads(response.content)["concordances"]
            returned_urls = [x["chant_link"] for x in returned_chants]
            self.assertCountEqual(
                [self.chants["published_chant"].get_absolute_url()], returned_urls
            )

    def test_concordance_items(self):
        cantus_id: str = "345678"
        chant: Chant = make_fake_chant(cantus_id=cantus_id)

        response: JsonResponse = self.client.get(
            reverse("ajax-melody", args=[cantus_id])
        )
        content: dict = json.loads(response.content)
        concordances: list = content["concordances"]
        concordance: dict = concordances[0]

        expected_items: ItemsView = {
            "siglum": chant.source.short_heading,
            "folio": chant.folio,
            "service__name": chant.service.name,
            "genre__name": chant.genre.name,
            "position": chant.position,
            "feast__name": chant.feast.name,
            "cantus_id": chant.cantus_id,
            "volpiano": chant.volpiano,
            "mode": chant.mode,
            "manuscript_full_text_std_spelling": chant.manuscript_full_text_std_spelling,
            "manuscript_syllabized_full_text": chant.manuscript_syllabized_full_text,
            "source_link": chant.source.get_absolute_url(),
            "ci_link": chant.get_ci_url(),
            "chant_link": chant.get_absolute_url(),
            "db": "CD",
        }.items()
        observed_keys: KeysView = concordance.keys()
        self.assertEqual(len(expected_items), len(observed_keys))

        for key, value in expected_items:
            with self.subTest(key=key):
                self.assertIn(key, observed_keys)
            with self.subTest(value=key):
                self.assertEqual(value, concordance[key])


class JsonMelodyExportTest(TestCase):
    def test_json_melody_response(self):
        NUM_CHANTS = 10
        FAKE_CANTUS_ID = "111111"
        for _ in range(NUM_CHANTS):
            make_fake_chant(cantus_id=FAKE_CANTUS_ID)

        response_1 = self.client.get(f"/json-melody/{FAKE_CANTUS_ID}")
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_1, JsonResponse)

        response_2 = self.client.get(
            reverse("json-melody-export", args=[FAKE_CANTUS_ID])
        )
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_2, JsonResponse)
        unpacked_response = json.loads(response_2.content)
        self.assertEqual(len(unpacked_response), NUM_CHANTS)

    def test_json_melody_fields(self):
        CORRECT_FIELDS = {
            "mid",
            "nid",
            "cid",
            "siglum",
            "srcnid",
            "folio",
            "incipit",
            "fulltext",
            "syllabized_full_text",
            "volpiano",
            "mode",
            "feast",
            "office",
            "genre",
            "position",
            "chantlink",
            "srclink",
        }
        FAKE_CANTUS_ID = "111111"
        make_fake_chant(cantus_id=FAKE_CANTUS_ID)
        response = self.client.get(reverse("json-melody-export", args=[FAKE_CANTUS_ID]))
        unpacked = json.loads(response.content)[0]
        response_fields = set(unpacked.keys())
        self.assertEqual(response_fields, CORRECT_FIELDS)

    def test_json_melody_published_vs_unpublished(self):
        FAKE_CANTUS_ID = "111111"
        published_source = make_fake_source(published=True)
        published_chant = make_fake_chant(
            cantus_id=FAKE_CANTUS_ID,
            manuscript_full_text_std_spelling="I'm a chant from a published source!",
            source=published_source,
        )
        unpublished_source = make_fake_source(published=False)
        unpublished_chant = make_fake_chant(
            cantus_id=FAKE_CANTUS_ID,
            manuscript_full_text_std_spelling="Help, I'm trapped in a JSON response factory! Can you help me escape...?",
            source=unpublished_source,
        )
        response = self.client.get(reverse("json-melody-export", args=[FAKE_CANTUS_ID]))
        unpacked_response = json.loads(response.content)
        self.assertEqual(len(unpacked_response), 1)  # just published_chant
        self.assertEqual(
            unpacked_response[0]["fulltext"], "I'm a chant from a published source!"
        )


class JsonNodeExportTest(TestCase):
    def test_json_node_response(self):
        chant = make_fake_chant()
        id = chant.id

        response_1 = self.client.get(f"/json-node/{id}")
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_1, JsonResponse)

        response_2 = self.client.get(reverse("json-node-export", args=[id]))
        self.assertEqual(response_2.status_code, 200)
        self.assertIsInstance(response_2, JsonResponse)

        response_3 = self.client.get(reverse("json-node-export", args=["1000000000"]))
        self.assertEqual(response_3.status_code, 404)

    def test_404_for_objects_created_in_newcantus(self):
        # json_node should only work for items created in OldCantus, where objects of different
        # types are all guaranteed to have unique IDs.
        # objects created in NewCantus should all have ID >= 1_000_000
        chant = make_fake_chant()
        chant.id = 1_000_001
        chant.save()

        response_3 = self.client.get(reverse("json-node-export", args=["1000001"]))
        self.assertEqual(response_3.status_code, 404)

    def test_json_node_for_chant(self):
        chant = make_fake_chant()
        id = chant.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_cantus_id = unpacked_response["cantus_id"]
        self.assertIsInstance(response_cantus_id, str)
        self.assertEqual(response_cantus_id, chant.cantus_id)

        response_id = unpacked_response["id"]
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_for_sequence(self):
        sequence = make_fake_sequence()
        id = sequence.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_cantus_id = unpacked_response["cantus_id"]
        self.assertIsInstance(response_cantus_id, str)
        self.assertEqual(response_cantus_id, sequence.cantus_id)

        response_id = unpacked_response["id"]
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_for_source(self):
        source = make_fake_source()
        id = source.id

        response = self.client.get(reverse("json-node-export", args=[id]))
        self.assertIsInstance(response, JsonResponse)

        unpacked_response = json.loads(response.content)

        response_shelfmark = unpacked_response["shelfmark"]
        self.assertIsInstance(response_shelfmark, str)
        self.assertEqual(response_shelfmark, source.shelfmark)

        response_id = unpacked_response["id"]
        self.assertIsInstance(response_id, int)
        self.assertEqual(response_id, id)

    def test_json_node_published_vs_unpublished(self):
        source = make_fake_source(published=True)
        chant = make_fake_chant(source=source)
        sequence = make_fake_sequence(source=source)

        source_id = source.id
        chant_id = chant.id
        sequence_id = sequence.id

        published_source_response = self.client.get(
            reverse("json-node-export", args=[source_id])
        )
        self.assertEqual(published_source_response.status_code, 200)
        published_chant_response = self.client.get(
            reverse("json-node-export", args=[chant_id])
        )
        self.assertEqual(published_chant_response.status_code, 200)
        published_sequence_response = self.client.get(
            reverse("json-node-export", args=[sequence_id])
        )
        self.assertEqual(published_sequence_response.status_code, 200)

        source.published = False
        source.save()

        unpublished_source_response = self.client.get(
            reverse("json-node-export", args=[source_id])
        )
        self.assertEqual(unpublished_source_response.status_code, 404)
        unpublished_chant_response = self.client.get(
            reverse("json-node-export", args=[chant_id])
        )
        self.assertEqual(unpublished_chant_response.status_code, 404)
        unpublished_sequence_response = self.client.get(
            reverse("json-node-export", args=[sequence_id])
        )
        self.assertEqual(unpublished_sequence_response.status_code, 404)


class NotationJsonTest(TestCase):
    def test_response(self):
        notation: Notation = make_fake_notation()
        id: int = notation.id

        response = self.client.get(reverse("notation-json-export", args=[id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, JsonResponse)

    def test_keys(self):
        notation: Notation = make_fake_notation()
        id: int = notation.id

        response = self.client.get(reverse("notation-json-export", args=[id]))
        response_json: dict = response.json()
        response_keys = response_json.keys()

        expected_keys = [
            "id",
            "name",
            "date_created",
            "date_updated",
            "created_by",
            "last_updated_by",
        ]
        for key in expected_keys:
            with self.subTest(key=key):
                self.assertIn(key, response_keys)


class ProvenanceJsonTest(TestCase):
    def test_response(self):
        provenance: Provenance = make_fake_provenance()
        id: int = provenance.id

        response = self.client.get(reverse("provenance-json-export", args=[id]))
        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response, JsonResponse)

    def test_keys(self):
        provenance: Provenance = make_fake_provenance()
        id: int = provenance.id

        response = self.client.get(reverse("provenance-json-export", args=[id]))
        response_json: dict = response.json()
        response_keys = response_json.keys()

        expected_keys = [
            "id",
            "name",
            "date_created",
            "date_updated",
            "created_by",
            "last_updated_by",
        ]
        for key in expected_keys:
            with self.subTest(key=key):
                self.assertIn(key, response_keys)


class JsonSourcesExportTest(TestCase):
    def setUp(self):
        # the JsonSourcesExport View uses the CANTUS Segment's .source_set property,
        # so we need to make sure to set up a CANTUS segment with the right ID for each test.
        self.cantus_segment = make_fake_segment(id=4063, name="Bower Sequence Database")
        self.bower_segment = make_fake_segment(id=4064, name="CANTUS Database")

    def test_json_sources_response(self):
        source = make_fake_source(published=True, segment=[self.cantus_segment])

        response_1 = self.client.get(f"/json-sources/")
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_1, JsonResponse)

        response_2 = self.client.get(reverse("json-sources-export"))
        self.assertEqual(response_2.status_code, 200)
        self.assertIsInstance(response_2, JsonResponse)

    def test_json_sources_format(self):
        NUMBER_OF_SOURCES = 10
        for _ in range(NUMBER_OF_SOURCES):
            _ = make_fake_source(published=True, segment=[self.cantus_segment])

        sample_source = Source.objects.all().order_by("?").first()

        # there should be one item for each source
        response = self.client.get(reverse("json-sources-export"))
        unpacked_response = json.loads(response.content)
        self.assertEqual(len(unpacked_response), NUMBER_OF_SOURCES)

        # for each item, the key should be the source's id and the value should be
        # a nested dictionary with a single key: "csv"
        sample_id = str(sample_source.id)
        self.assertIn(sample_id, unpacked_response.keys())
        sample_item = unpacked_response[sample_id]
        sample_item_keys = list(sample_item.keys())
        self.assertEqual(sample_item_keys, ["csv"])

        # the single value should be a link in form `cantusdatabase.com/csv/{source.id}`
        expected_substring = f"source/{sample_id}/csv"
        sample_item_value = list(sample_item.values())[0]
        self.assertIn(expected_substring, sample_item_value)

    def test_json_sources_published_vs_unpublished(self):
        NUM_PUBLISHED_SOURCES = 3
        NUM_UNPUBLISHED_SOURCES = 5
        for _ in range(NUM_PUBLISHED_SOURCES):
            _ = make_fake_source(published=True, segment=[self.cantus_segment])
        for _ in range(NUM_UNPUBLISHED_SOURCES):
            _ = make_fake_source(published=False, segment=[self.cantus_segment])

        sample_published_source = (
            Source.objects.filter(published=True).order_by("?").first()
        )
        sample_unpublished_source = (
            Source.objects.filter(published=False).order_by("?").first()
        )

        response = self.client.get(reverse("json-sources-export"))
        unpacked_response = json.loads(response.content)
        response_keys = unpacked_response.keys()
        self.assertEqual(len(unpacked_response), NUM_PUBLISHED_SOURCES)

        published_id = str(sample_published_source.id)
        unpublished_id = str(sample_unpublished_source.id)
        self.assertIn(published_id, response_keys)
        self.assertNotIn(unpublished_id, response_keys)

    def test_only_sources_from_cantus_segment_appear_in_results(self):
        NUM_CANTUS_SOURCES = 5
        NUM_BOWER_SOURCES = 7
        for _ in range(NUM_CANTUS_SOURCES):
            _ = make_fake_source(published=True, segment=[self.cantus_segment])
        for _ in range(NUM_BOWER_SOURCES):
            _ = make_fake_source(published=True, segment=[self.bower_segment])

        sample_cantus_source = (
            Source.objects.filter(segment_m2m=self.cantus_segment).order_by("?").first()
        )
        sample_bower_source = (
            Source.objects.filter(segment_m2m=self.bower_segment).order_by("?").first()
        )

        response = self.client.get(reverse("json-sources-export"))
        unpacked_response = json.loads(response.content)
        response_keys = unpacked_response.keys()
        self.assertEqual(len(unpacked_response), NUM_CANTUS_SOURCES)

        cantus_id = str(sample_cantus_source.id)
        bower_id = str(sample_bower_source.id)
        self.assertIn(cantus_id, response_keys)
        self.assertNotIn(bower_id, response_keys)


class JsonNextChantsTest(TestCase):
    def test_existing_cantus_id(self):
        fake_source_1 = make_fake_source()
        fake_source_2 = make_fake_source()

        fake_chant_2 = make_fake_chant(
            source=fake_source_1,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_1 = make_fake_chant(
            source=fake_source_1,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_2,
        )

        fake_chant_4 = make_fake_chant(
            source=fake_source_2,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_3 = make_fake_chant(
            source=fake_source_2,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_4,
        )

        path = reverse("json-nextchants", args=["1000"])
        response = self.client.get(path)
        self.assertIsInstance(response, JsonResponse)
        unpacked_response = json.loads(response.content)
        self.assertEqual(unpacked_response, {"2000": 2})

    def test_nonexistent_cantus_id(self):
        fake_source_1 = make_fake_source()
        fake_source_2 = make_fake_source()

        fake_chant_2 = make_fake_chant(
            source=fake_source_1,
        )
        fake_chant_1 = make_fake_chant(source=fake_source_1, next_chant=fake_chant_2)

        fake_chant_4 = make_fake_chant(
            source=fake_source_2,
        )
        fake_chant_3 = make_fake_chant(source=fake_source_2, next_chant=fake_chant_4)

        path = reverse("json-nextchants", args=["9000"])
        response = self.client.get(reverse("json-nextchants", args=["9000"]))
        self.assertIsInstance(response, JsonResponse)
        unpacked_response = json.loads(response.content)
        self.assertEqual(unpacked_response, {})

    def test_published_vs_unpublished(self):
        fake_source_1 = make_fake_source(published=True)
        fake_source_2 = make_fake_source(published=False)

        fake_chant_2 = make_fake_chant(
            source=fake_source_1,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_1 = make_fake_chant(
            source=fake_source_1,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_2,
        )

        fake_chant_4 = make_fake_chant(
            source=fake_source_2,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_3 = make_fake_chant(
            source=fake_source_2,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_4,
        )

        path = reverse("json-nextchants", args=["1000"])
        response_1 = self.client.get(path)
        self.assertIsInstance(response_1, JsonResponse)
        unpacked_response_1 = json.loads(response_1.content)
        self.assertEqual(unpacked_response_1, {"2000": 1})

        fake_source_2.published = True
        fake_source_2.save()
        response_2 = self.client.get(path)
        self.assertIsInstance(response_2, JsonResponse)
        unpacked_response_2 = json.loads(response_2.content)
        self.assertEqual(unpacked_response_2, {"2000": 2})


class JsonCidTest(TestCase):
    def test_published_vs_unpublished(self):
        published_source = make_fake_source(published=True)
        published_chant = make_fake_chant(
            cantus_id="123.publ",
            source=published_source,
        )
        pub_response = self.client.get(
            reverse("json-cid-export", args=["123.publ"]),
        )
        pub_json = pub_response.json()
        pub_chants = pub_json["chants"]
        self.assertEqual(len(pub_chants), 1)

        unpublished_source = make_fake_source(published=False)
        unpublished_chant = make_fake_chant(
            cantus_id="456.unpub",
            source=unpublished_source,
        )
        unpub_response = self.client.get(
            reverse("json-cid-export", args=["456.unpub"]),
        )
        unpub_json = unpub_response.json()
        unpub_chants = unpub_json["chants"]
        self.assertEqual(len(unpub_chants), 0)

    def test_chant_vs_sequence(self):
        chant = make_fake_chant(cantus_id="123456")
        response_1 = self.client.get(
            reverse("json-cid-export", args=["123456"]),
        )
        json_1 = response_1.json()
        chants_1 = json_1["chants"]
        self.assertEqual(len(chants_1), 1)

        sequence = make_fake_sequence(cantus_id="123456")
        response_2 = self.client.get(
            reverse("json-cid-export", args=["123456"]),
        )
        json_2 = response_2.json()
        chants_2 = json_2["chants"]
        self.assertEqual(
            len(chants_2), 1
        )  # should return the chant, but not the sequence

        chant.delete()
        response_3 = self.client.get(
            reverse("json-cid-export", args=["123456"]),
        )
        json_3 = response_3.json()
        chants_3 = json_3["chants"]
        self.assertEqual(len(chants_3), 0)  # should not return the sequence

    def test_structure(self):
        """
        should be structured thus:
        {
            "chants": [
                "chant": {
                    "siglum": "some string"
                    "srclink": "some string"
                    "chantlink": "some string"
                    "folio": "some string"
                    "sequence": some_integer
                    "incipit": "some string"
                    "feast": "some string"
                    "genre": "some string"
                    "office": "some string"
                    "position": "some string"
                    "cantus_id": "some string"
                    "image": "some string"
                    "mode": "some string"
                    "full_text": "some string"
                    "melody": "some string"
                    "db": "CD"
                },
                "chant": {
                    etc.
                },
            ]
        }
        A more complete specification can be found at
        https://github.com/DDMAL/CantusDB/issues/1170.
        """
        for _ in range(7):
            make_fake_chant(cantus_id="3.14159")
        response = self.client.get(
            reverse("json-cid-export", args=["3.14159"]),
        )
        json_obj = response.json()
        json_keys = json_obj.keys()
        self.assertEqual(list(json_keys), ["chants"])

        chants = json_obj["chants"]
        self.assertIsInstance(chants, list)
        self.assertEqual(len(chants), 7)

        first_item = chants[0]
        item_keys = first_item.keys()
        self.assertIsInstance(first_item, dict)
        self.assertEqual(list(item_keys), ["chant"])

        first_chant = first_item["chant"]
        chant_keys = first_chant.keys()
        expected_keys = {
            "siglum",
            "srclink",
            "chantlink",
            "folio",
            "sequence",
            "incipit",
            "feast",
            "genre",
            "office",
            "position",
            "cantus_id",
            "image",
            "mode",
            "full_text",
            "melody",
            "db",
        }
        self.assertEqual(set(chant_keys), expected_keys)

    def test_values(self):
        chant = make_fake_chant(cantus_id="100000")

        expected_values = {
            "siglum": chant.source.short_heading,
            "srclink": f"http://testserver/source/{chant.source.id}/",
            "chantlink": f"http://testserver/chant/{chant.id}/",
            "folio": chant.folio,
            "sequence": chant.c_sequence,
            "incipit": chant.incipit,
            "feast": chant.feast.name,
            "genre": chant.genre.name,
            "office": chant.service.name,
            "position": chant.position,
            "mode": chant.mode,
            "image": chant.image_link,
            "melody": chant.volpiano,
            "full_text": chant.manuscript_full_text_std_spelling,
            "db": "CD",
        }
        response_1 = self.client.get(
            reverse("json-cid-export", args=["100000"]),
        )
        json_for_one_chant_1 = response_1.json()["chants"][0]["chant"]
        for key in expected_values.keys():
            self.assertEqual(expected_values[key], json_for_one_chant_1[key])

        chant.manuscript_full_text = None
        chant.manuscript_full_text_std_spelling = None
        chant.folio = None
        chant.incipit = None
        chant.feast = None
        chant.genre = None
        chant.service = None
        chant.position = None
        chant.mode = None
        chant.image_link = None
        chant.volpiano = None
        chant.manuscript_full_text_std_spelling = None
        chant.save()

        response_2 = self.client.get(
            reverse("json-cid-export", args=["100000"]),
        )
        json_for_one_chant_2 = response_2.json()["chants"][0]["chant"]

        sequence_value = json_for_one_chant_2.pop("sequence")
        self.assertIsInstance(sequence_value, int)

        for key, value in json_for_one_chant_2.items():
            with self.subTest(key=key):
                self.assertIsInstance(
                    value,
                    str,  # we've already removed ["sequence"], which should
                    # be an int. All other keys should be strings, and there should
                    # be no Nones or nulls
                )

        chant.manuscript_full_text = "nahn-staendrd spillynge"
        chant.manuscript_full_text_std_spelling = "standard spelling"
        chant.save()
        response_3 = self.client.get(
            reverse("json-cid-export", args=["100000"]),
        )
        json_for_one_chant_3 = response_3.json()["chants"][0]["chant"]
        self.assertEqual(json_for_one_chant_3["full_text"], "standard spelling")


def get_filename_from_response(response: HttpResponse) -> str:
    """Return the filename ``Content-Disposition`` asks the browser to save as.

    Handles both forms Django emits: a quoted ASCII ``filename`` and the
    percent-encoded ``filename*`` it falls back to when the name is not ASCII.
    """
    disposition = response["Content-Disposition"]
    if encoded_match := re.match(
        r"attachment; filename\*=utf-8''(?P<name>.+)$", disposition, re.IGNORECASE
    ):
        return unquote(encoded_match["name"])
    quoted_match = re.match(r'attachment; filename="(?P<name>.*)"$', disposition)
    if quoted_match is None:
        raise AssertionError(f"unexpected Content-Disposition: {disposition}")
    return quoted_match["name"]


class CsvExportTest(CustomAccessTestMixin, TestCase):
    def test_url(self):
        institution = make_fake_institution(siglum="A-Gu")
        source = make_fake_source(
            published=True, holding_institution=institution, shelfmark="Ms. 211"
        )
        response_1 = self.client.get(reverse("csv-export", args=[source.id]))
        self.assertEqual(response_1.status_code, 200)
        self.assertEqual(
            response_1["Content-Disposition"],
            f'attachment; filename="{source.id}-A-Gu Ms. 211.csv"',
        )

    def test_url_without_holding_institution(self):
        source = make_fake_source(
            published=True, holding_institution=None, shelfmark="Ms. 211"
        )
        response = self.client.get(reverse("csv-export", args=[source.id]))

        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="{source.id}-Cantus Ms. 211.csv"',
        )

    def test_url_filename_sanitizes_path_separators(self):
        institution = make_fake_institution(siglum="A-Gu")
        source = make_fake_source(
            published=True, holding_institution=institution, shelfmark="Ms. 12/1"
        )
        response = self.client.get(reverse("csv-export", args=[source.id]))

        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="{source.id}-A-Gu Ms. 12-1.csv"',
        )

    def test_url_filename_sanitizes_characters_windows_disallows(self):
        institution = make_fake_institution(siglum="A-Gu")
        source = make_fake_source(
            published=True,
            holding_institution=institution,
            shelfmark='Ms. 12<>:"|?*1',
        )
        response = self.client.get(reverse("csv-export", args=[source.id]))

        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="{source.id}-A-Gu Ms. 12-1.csv"',
        )

    def test_url_filename_sanitizes_control_characters(self):
        # A newline reaching the header value would make Django raise
        # BadHeaderError, so control characters must be replaced too.
        institution = make_fake_institution(siglum="A-Gu")
        source = make_fake_source(
            published=True, holding_institution=institution, shelfmark="Ms.\n211"
        )
        response = self.client.get(reverse("csv-export", args=[source.id]))

        self.assertEqual(
            response["Content-Disposition"],
            f'attachment; filename="{source.id}-A-Gu Ms.-211.csv"',
        )

    def test_url_filename_truncates_long_shelfmarks(self):
        institution = make_fake_institution(siglum="A-Gu")
        source = make_fake_source(
            published=True,
            holding_institution=institution,
            shelfmark="M" * 255,  # the maximum length of the shelfmark field
        )
        response = self.client.get(reverse("csv-export", args=[source.id]))

        filename = get_filename_from_response(response)
        # 255 bytes is the per-filename limit on Windows, macOS and Linux alike.
        self.assertLessEqual(len(filename.encode("utf-8")), 255)
        self.assertTrue(filename.startswith(f"{source.id}-A-Gu M"))
        self.assertTrue(filename.endswith(".csv"))

    def test_url_filename_keeps_non_ascii_characters(self):
        institution = make_fake_institution(siglum="F-Pn")
        source = make_fake_source(
            published=True, holding_institution=institution, shelfmark="Ms. Réserve 1"
        )
        response = self.client.get(reverse("csv-export", args=[source.id]))

        # Accented characters are legitimate in shelfmarks, so they are kept
        # rather than stripped; Django percent-encodes them per RFC 5987.
        self.assertEqual(
            get_filename_from_response(response),
            f"{source.id}-F-Pn Ms. Réserve 1.csv",
        )

    def test_content(self):
        NUM_CHANTS = 5
        source_shelfmark = "SourceShelfmark"
        chant_siglum = "ChantSiglum"  # OldCantus chants/sequences had a "siglum"
        # field, which would sometimes get out of date when the chant's source's siglum
        # was updated. We keep the chant siglum field around to ensure no data is
        # inadvertently lost, but we need to ensure it is never displayed publicly.
        source = make_fake_source(published=True, shelfmark=source_shelfmark)
        for _ in range(NUM_CHANTS):
            chant = make_fake_chant(source=source)
            chant.siglum = chant_siglum
            chant.save()
        response = self.client.get(reverse("csv-export", args=[source.id]))
        content = response.content.decode("utf-8")
        split_content = list(csv.reader(content.splitlines(), delimiter=","))
        header, rows = split_content[0], split_content[1:]

        expected_column_titles = [
            "shelfmark",
            "holding_institution",
            "marginalia",
            "folio",
            "sequence",
            "incipit",
            "feast",
            "service",
            "genre",
            "position",
            "cantus_id",
            "mode",
            "finalis",
            "differentia",
            "differentiae_database",
            "fulltext_standardized",
            "fulltext_ms",
            "syllabized_full_text",
            "volpiano",
            "image_link",
            "melody_id",
            "addendum",
            "extra",
            "node_id",
        ]
        for t in expected_column_titles:
            with self.subTest(expected_column=t):
                self.assertIn(t, header)
        with self.subTest(subtest="ensure a row exists for each chant"):
            self.assertEqual(len(rows), NUM_CHANTS)
        with self.subTest(
            subtest="ensure all rows have the same number of columns as the header"
        ):
            for row in rows:
                self.assertEqual(len(header), len(row))
        with self.subTest(
            "ensure we only ever display chants' sources' shelfmark, and never the "
            "value stored in chants' siglum fields"
        ):
            for row in rows:
                self.assertEqual(row[0], source_shelfmark)

    def test_permissions(self) -> None:
        published_source = make_fake_source(published=True)
        unassigned_source = make_fake_source(published=False)
        user_assigned_source = make_fake_source(
            published=False, current_editors=[self.users["user"]]
        )
        with self.subTest("Test published source"):
            self.client.logout()
            response = self.client.get(
                reverse("csv-export", args=[published_source.id])
            )
            self.assertEqual(response.status_code, 200)
        with self.subTest("Test unassigned source"):
            response = self.client.get(
                reverse("csv-export", args=[unassigned_source.id])
            )
            self.assertEqual(response.status_code, 403)
            self.client.force_login(self.users["user"])
            response = self.client.get(
                reverse("csv-export", args=[unassigned_source.id])
            )
            self.assertEqual(response.status_code, 403)
            self.client.force_login(self.users["editor"])
            response = self.client.get(
                reverse("csv-export", args=[unassigned_source.id])
            )
            self.assertEqual(response.status_code, 403)
            self.client.force_login(self.users["superuser"])
            response = self.client.get(
                reverse("csv-export", args=[unassigned_source.id])
            )
            self.assertEqual(response.status_code, 200)
            self.client.force_login(self.users["global viewer"])
            response = self.client.get(
                reverse("csv-export", args=[unassigned_source.id])
            )
            self.assertEqual(response.status_code, 200)
        with self.subTest("Test user assigned source"):
            self.client.logout()
            response = self.client.get(
                reverse("csv-export", args=[user_assigned_source.id])
            )
            self.assertEqual(response.status_code, 403)
            self.client.force_login(self.users["user"])
            response = self.client.get(
                reverse("csv-export", args=[user_assigned_source.id])
            )
            self.assertEqual(response.status_code, 200)
            self.client.force_login(self.users["editor"])
            response = self.client.get(
                reverse("csv-export", args=[user_assigned_source.id])
            )
            self.assertEqual(response.status_code, 403)
            self.client.force_login(self.users["superuser"])
            response = self.client.get(
                reverse("csv-export", args=[user_assigned_source.id])
            )
            self.assertEqual(response.status_code, 200)
            self.client.force_login(self.users["global viewer"])
            response = self.client.get(
                reverse("csv-export", args=[user_assigned_source.id])
            )
            self.assertEqual(response.status_code, 200)

    def test_csv_export_on_source_with_sequences(self):
        NUM_SEQUENCES = 5
        bower_segment = make_fake_segment(name="Bower Sequence Database")
        bower_segment.id = 4064
        bower_segment.save()
        source = make_fake_source(published=True)
        source.segment_m2m.add(bower_segment)
        for _ in range(NUM_SEQUENCES):
            make_fake_sequence(source=source)
        response = self.client.get(reverse("csv-export", args=[source.id]))
        content = response.content.decode("utf-8")
        split_content = list(csv.reader(content.splitlines(), delimiter=","))
        header, rows = split_content[0], split_content[1:]

        with self.subTest(subtest="ensure a row exists for each sequence"):
            self.assertEqual(len(rows), NUM_SEQUENCES)
        with self.subTest(
            subtest="ensure all rows have the same number of columns as the header"
        ):
            for row in rows:
                self.assertEqual(len(header), len(row))
        with self.subTest(
            subtest="ensure .s_sequence field is being written to the 'sequence' column"
        ):
            for row in rows:
                self.assertNotEqual(row[3], "")


cid_concordances_mock_requests_data = {
    "https://cantusindex.uwaterloo.ca/json-cid/008349": MagicMock(
        **{
            "json.return_value": mock_json_cid_008349_json,
            "status_code": 200,
            "text.strip.return_value": 1,  # Set this so cantusindex.get_json_from_ci_api
            # does not return None
        }
    ),
    "https://cantusindex.uwaterloo.ca/json-cid/006928": MagicMock(
        **{
            "json.return_value": mock_json_cid_006928_json,
            "text.strip.return_value": 1,
            "status_code": 200,
        },
    ),
    "https://cantusindex.uwaterloo.ca/json-cid/000000": MagicMock(
        **{
            "json.return_value": {"databases": {}, "chants": {}},
            "text.strip.return_value": 1,
            "status_code": 200,
        },
    ),
    "https://gregorien.info/chant/cid/008349/en": MagicMock(status_code=404),
    "https://gregorien.info/chant/cid/006928/en": MagicMock(status_code=200),
    "https://gregorien.info/chant/cid/000000/en": MagicMock(status_code=404),
}


def cid_concordances_requests_value(url: str, timeout: int) -> dict[str, Any]:
    return cid_concordances_mock_requests_data[url]


class CIDConcordancesTest(TestCase):
    # A dictionary containing the data expected from the API
    # calls made by the view. The keys are the URLs of the API
    # calls, and the values are the data returned by the API.

    @patch("requests.get", MagicMock(side_effect=cid_concordances_requests_value))
    def test_view(self) -> None:
        with self.subTest("Concordances exist on Cantus Index and Gregorien"):
            response = self.client.get(
                reverse("cid-concordances"), data={"cantus_id": "006928"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["databases"]), 2)
            self.assertEqual(len(response.json()["chants"]), 2)
        with self.subTest("Concordances exist on Cantus Index but not Gregorien"):
            response = self.client.get(
                reverse("cid-concordances"), data={"cantus_id": "008349"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["databases"]), 1)
            self.assertEqual(len(response.json()["chants"]), 2)
        with self.subTest("No concordances"):
            response = self.client.get(
                reverse("cid-concordances"), data={"cantus_id": "000000"}
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(len(response.json()["databases"]), 0)
            self.assertEqual(len(response.json()["chants"]), 0)
