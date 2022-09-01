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

class OfficeListViewTest(TestCase):
    fixtures = ["office_fixtures.json"]
    PAGE_SIZE = OfficeListView.paginate_by

    def setUp(self):
        self.number_of_offices = Office.objects.all().count()
        return super().setUp()

    def test_view_url_path(self):
        response = self.client.get("/offices/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("office-list"))
        self.assertEqual(response.status_code, 200)

    def test_view_correct_templates(self):
        response = self.client.get(reverse("office-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "office_list.html")

    def test_pagination(self):
        # To get total number of pages do a ceiling integer division
        q, r = divmod(self.number_of_offices, self.PAGE_SIZE)
        pages = q + bool(r)

        # Test all pages
        for page_num in range(1, pages + 1):
            response = self.client.get(reverse("office-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue("is_paginated" in response.context)
            if self.number_of_offices > self.PAGE_SIZE:
                self.assertTrue(response.context["is_paginated"])
            else:
                self.assertFalse(response.context["is_paginated"])
            if page_num == pages and (self.number_of_offices % self.PAGE_SIZE != 0):
                self.assertEqual(
                    len(response.context["offices"]),
                    self.number_of_offices % self.PAGE_SIZE,
                )
            else:
                self.assertEqual(len(response.context["offices"]), self.PAGE_SIZE)

        # Test the "last" syntax
        response = self.client.get(reverse("office-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)

        # Test some invalid values for pages
        response = self.client.get(reverse("office-list"), {"page": -1})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("office-list"), {"page": 0})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("office-list"), {"page": "lst"})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("office-list"), {"page": pages + 1})
        self.assertEqual(response.status_code, 404)


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
