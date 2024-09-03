"""
Tests for views in views/api.py
"""

import json
from typing import Optional
import csv
from collections.abc import ItemsView, KeysView

from django.test import TestCase
from django.urls import reverse
from django.http import JsonResponse

from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_sequence,
    make_fake_source,
    make_fake_notation,
    make_fake_provenance,
    make_fake_segment,
)
from main_app.models import Chant, Source, Provenance, Notation


class AjaxSearchBarTest(TestCase):
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
        chant_with_normal_cantus_id = make_fake_chant(
            cantus_id="012345",
            manuscript_full_text_std_spelling="This fulltext contains no numerals",
        )
        chant_with_numerals_in_incipit = make_fake_chant(
            cantus_id="123456",
            manuscript_full_text_std_spelling="0 me! 0 my! This is unexpected!",
        )

        # for search terms that contain numerals, we should only return
        # matches with the cantus_id field, and not the incipit field
        matching_search_term = "0"
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
        non_matching_search_term = "2"
        non_matching_response = self.client.get(
            reverse("ajax-search-bar", args=[non_matching_search_term])
        )
        non_matching_content = json.loads(non_matching_response.content)
        non_matching_chants = non_matching_content["chants"]
        self.assertEqual(len(non_matching_chants), 0)


class AjaxMelodyViewTest(TestCase):
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

    def test_published_vs_unpublished(self):
        cantus_id: str = "234567"

        published_source: Source = make_fake_source(published=True)
        num_matching_published_chants: int = 3
        for _ in range(num_matching_published_chants):
            make_fake_chant(
                cantus_id=cantus_id,
                source=published_source,
            )

        unpublished_source: Source = make_fake_source(published=False)
        num_matching_unpublished_chants: int = 5
        for _ in range(num_matching_unpublished_chants):
            make_fake_chant(
                cantus_id=cantus_id,
                source=unpublished_source,
            )

        num_nonmatching_published_chants: int = 2
        for _ in range(num_nonmatching_published_chants):
            make_fake_chant(
                cantus_id="123456",
                source=published_source,
            )

        response: JsonResponse = self.client.get(
            reverse("ajax-melody", args=[cantus_id])
        )
        content: dict = json.loads(response.content)
        concordances: list = content["concordances"]
        concordance_count: int = content["concordance_count"]

        self.assertEqual(concordance_count, num_matching_published_chants)
        self.assertEqual(len(concordances), num_matching_published_chants)

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
            "holding_institution",
            "shelfmark",
            "srcnid",
            "folio",
            "incipit",
            "fulltext",
            "volpiano",
            "mode",
            "feast",
            "service",
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
        source = make_fake_source(published=True, segment=self.cantus_segment)

        response_1 = self.client.get(f"/json-sources/")
        self.assertEqual(response_1.status_code, 200)
        self.assertIsInstance(response_1, JsonResponse)

        response_2 = self.client.get(reverse("json-sources-export"))
        self.assertEqual(response_2.status_code, 200)
        self.assertIsInstance(response_2, JsonResponse)

    def test_json_sources_format(self):
        NUMBER_OF_SOURCES = 10
        for _ in range(NUMBER_OF_SOURCES):
            _ = make_fake_source(published=True, segment=self.cantus_segment)

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
            _ = make_fake_source(published=True, segment=self.cantus_segment)
        for _ in range(NUM_UNPUBLISHED_SOURCES):
            _ = make_fake_source(published=False, segment=self.cantus_segment)

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
            _ = make_fake_source(published=True, segment=self.cantus_segment)
        for _ in range(NUM_BOWER_SOURCES):
            _ = make_fake_source(published=True, segment=self.bower_segment)

        sample_cantus_source = (
            Source.objects.filter(segment=self.cantus_segment).order_by("?").first()
        )
        sample_bower_source = (
            Source.objects.filter(segment=self.bower_segment).order_by("?").first()
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

        fake_chant_2 = Chant.objects.create(
            source=fake_source_1,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_1 = Chant.objects.create(
            source=fake_source_1,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_2,
        )

        fake_chant_4 = Chant.objects.create(
            source=fake_source_2,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_3 = Chant.objects.create(
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

        fake_chant_2 = Chant.objects.create(
            source=fake_source_1,
        )
        fake_chant_1 = Chant.objects.create(
            source=fake_source_1, next_chant=fake_chant_2
        )

        fake_chant_4 = Chant.objects.create(
            source=fake_source_2,
        )
        fake_chant_3 = Chant.objects.create(
            source=fake_source_2, next_chant=fake_chant_4
        )

        path = reverse("json-nextchants", args=["9000"])
        response = self.client.get(reverse("json-nextchants", args=["9000"]))
        self.assertIsInstance(response, JsonResponse)
        unpacked_response = json.loads(response.content)
        self.assertEqual(unpacked_response, {})

    def test_published_vs_unpublished(self):
        fake_source_1 = make_fake_source(published=True)
        fake_source_2 = make_fake_source(published=False)

        fake_chant_2 = Chant.objects.create(
            source=fake_source_1,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_1 = Chant.objects.create(
            source=fake_source_1,
            cantus_id="1000",
            folio="001r",
            c_sequence=1,
            next_chant=fake_chant_2,
        )

        fake_chant_4 = Chant.objects.create(
            source=fake_source_2,
            cantus_id="2000",
            folio="001r",
            c_sequence=2,
        )

        fake_chant_3 = Chant.objects.create(
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
                    "service": "some string"
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
            "service",
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
            "srclink": f"http://testserver/source/{chant.source.id}",
            "chantlink": f"http://testserver/chant/{chant.id}",
            "folio": chant.folio,
            "sequence": chant.c_sequence,
            "incipit": chant.incipit,
            "feast": chant.feast.name,
            "genre": chant.genre.name,
            "service": chant.service.name,
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


class CsvExportTest(TestCase):
    def test_url(self):
        source = make_fake_source(published=True)
        response_1 = self.client.get(reverse("csv-export", args=[source.id]))
        self.assertEqual(response_1.status_code, 200)

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

    def test_published_vs_unpublished(self):
        published_source = make_fake_source(published=True)
        response_1 = self.client.get(reverse("csv-export", args=[published_source.id]))
        self.assertEqual(response_1.status_code, 200)
        unpublished_source = make_fake_source(published=False)
        response_2 = self.client.get(
            reverse("csv-export", args=[unpublished_source.id])
        )
        self.assertEqual(response_2.status_code, 403)

    def test_csv_export_on_source_with_sequences(self):
        NUM_SEQUENCES = 5
        bower_segment = make_fake_segment(name="Bower Sequence Database")
        bower_segment.id = 4064
        bower_segment.save()
        source = make_fake_source(published=True)
        source.segment = bower_segment
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
