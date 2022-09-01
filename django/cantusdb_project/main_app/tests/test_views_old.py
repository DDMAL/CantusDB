import os
import random

from abc import abstractmethod
from abc import ABC
from django.test import TestCase
from django.urls import reverse
from faker import Faker
from typing import List
from main_app.models import Feast, Genre, Indexer, Office
from main_app.views import (
    FeastListView,
    GenreListView,
    IndexerListView,
    OfficeListView,
)

from . import make_fakes


# test_views_old (this file) is out of date and should not be run.
# Instead, run test_views and test_models.

fake = Faker()


# class ChantSearchViewTest(TestCase):
#     fixture_file = random.choice(
#         os.listdir(
#             "/code/django/cantusdb_project/main_app/fixtures/chants_fixed"
#         )
#     )
#     # Loading pretty much all fixtures since Chants refer to all of these,
#     # without them there are errors
#     fixtures = [
#         "provenance_fixtures.json",
#         "indexer_fixtures.json",
#         "century_fixtures.json",
#         "notation_fixtures.json",
#         "rism_siglum_fixtures.json",
#         "genre_fixtures.json",
#         "feast_fixtures.json",
#         "office_fixtures.json",
#         "segment_fixtures.json",
#         "source_fixtures.json",
#         f"chants_fixed/{fixture_file}",
#     ]

#     def setUp(self):
#         print (Chant.objects.all().count())

#     def test_view_url_path(self):
#         response = self.client.get("/chant-search/")
#         self.assertEqual(response.status_code, 200)

#     def test_view_url_reverse_name(self):
#         response = self.client.get(reverse("chant-search"))
#         self.assertEqual(response.status_code, 200)

#     def test_view_correct_templates(self):
#         response = self.client.get(reverse("chant-search"))
#         self.assertTemplateUsed(response, "base.html")
#         self.assertTemplateUsed(response, "chant_search.html")
