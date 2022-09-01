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


class OfficeDetailViewTest(TestCase):
    fixtures = ["office_fixtures.json"]
    SLICE_SIZE = 10

    def setUp(self):
        self.number_of_offices = Office.objects.all().count()
        self.slice_begin = random.randint(0, self.number_of_offices - self.SLICE_SIZE)
        self.slice_end = self.slice_begin + self.SLICE_SIZE
        return super().setUp()

    def test_view_url_path(self):
        for office in Office.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(f"/offices/{office.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for office in Office.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("office-detail", args=[office.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_correct_templates(self):
        for office in Office.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("office-detail", args=[office.id]))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "base.html")
            self.assertTemplateUsed(response, "office_detail.html")

    def test_view_context_data(self):
        for office in Office.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("office-detail", args=[office.id]))
            self.assertTrue("office" in response.context)
            self.assertEqual(office, response.context["office"])


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
