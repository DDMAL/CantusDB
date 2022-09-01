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


class FeastListViewTest(TestCase):
    PAGE_SIZE = FeastListView.paginate_by
    MIN_PAGES = 1
    MAX_PAGES = 6

    @classmethod
    def setUpTestData(cls):
        # Create at least 100 + [1,99] indexers, this way we can test pagination since
        # we're paginating by 100 items
        cls.number_of_indexers = cls.PAGE_SIZE * random.randint(
            cls.MIN_PAGES, cls.MAX_PAGES
        ) + random.randint(1, cls.PAGE_SIZE)

        for i in range(cls.number_of_indexers):
            make_fakes.make_fake_indexer()

    fixtures = ["feast_fixtures.json"]

    def setUp(self):
        self.number_of_feasts = Feast.objects.all().count()
        return super().setUp()

    # TODO: maybe make a more general method to test pagination that I can apply
    # to all list views?
    def test_pagination(self):
        # To get total number of pages do a ceiling integer division
        q, r = divmod(self.number_of_feasts, self.PAGE_SIZE)
        pages = q + bool(r)

        # Test all pages
        for page_num in range(1, pages + 1):
            response = self.client.get(reverse("feast-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue("is_paginated" in response.context)
            self.assertTrue(response.context["is_paginated"])
            if page_num == pages and (self.number_of_feasts % self.PAGE_SIZE != 0):
                self.assertEqual(
                    len(response.context["feasts"]),
                    self.number_of_feasts % self.PAGE_SIZE,
                )
            else:
                self.assertEqual(len(response.context["feasts"]), self.PAGE_SIZE)

        # Test the "last" syntax
        response = self.client.get(reverse("feast-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)

        # Test some invalid values for pages
        response = self.client.get(reverse("feast-list"), {"page": -1})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": 0})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": "lst"})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": pages + 1})
        self.assertEqual(response.status_code, 404)

    def test_filter_by_month(self):
        for i in range(1, 13):
            month = str(i)
            response = self.client.get(reverse("feast-list"), {"month": month})
            self.assertEqual(response.status_code, 200)
            feasts = response.context["paginator"].object_list
            # Check if all the feasts in the queryset have the month specified
            self.assertTrue(all(feast.month == i for feast in feasts))

    def test_ordering(self):
        # Order by feast_code
        response = self.client.get(reverse("feast-list"), {"ordering": "feast_code"})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "feast_code")

        # Order by name
        response = self.client.get(reverse("feast-list"), {"ordering": "name"})
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "name")

        # Empty ordering parameters in GET request should default to ordering
        # by name
        response = self.client.get(reverse("feast-list"), {"ordering": ""})
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "name")

        # Anything other than name and feast_code should default to ordering by
        # name
        response = self.client.get(
            reverse("feast-list"), {"ordering": random.randint(1, 100)}
        )
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "name")

        response = self.client.get(
            reverse("feast-list"), {"ordering": fake.text(max_nb_chars=20)}
        )
        feasts = response.context["paginator"].object_list
        self.assertEqual(feasts.query.order_by[0], "name")


class FeastDetailViewTest(TestCase):
    fixtures = ["feast_fixtures.json"]
    SLICE_SIZE = 10

    def setUp(self):
        self.number_of_feasts = Feast.objects.all().count()
        self.slice_begin = random.randint(0, self.number_of_feasts - self.SLICE_SIZE)
        self.slice_end = self.slice_begin + self.SLICE_SIZE
        return super().setUp()

    def test_view_url_path(self):
        for feast in Feast.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(f"/feasts/{feast.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for feast in Feast.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("feast-detail", args=[feast.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_correct_templates(self):
        for feast in Feast.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("feast-detail", args=[feast.id]))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "base.html")
            self.assertTemplateUsed(response, "feast_detail.html")

    def test_view_context_data(self):
        for feast in Feast.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("feast-detail", args=[feast.id]))
            self.assertTrue("feast" in response.context)
            self.assertEqual(feast, response.context["feast"])


class GenreListViewTest(TestCase):
    PAGE_SIZE = GenreListView.paginate_by
    fixtures = ["genre_fixtures.json"]

    def setUp(self):
        self.number_of_genres = Genre.objects.all().count()
        return super().setUp()

    def test_view_url_path(self):
        response = self.client.get("/genres/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(response.status_code, 200)

    def test_view_correct_templates(self):
        response = self.client.get(reverse("genre-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "genre_list.html")

    def test_filter_by_mass_or_office(self):
        response = self.client.get(reverse("genre-list"), {"mass_office": "Mass"})
        self.assertEqual(response.status_code, 200)
        genres = response.context["paginator"].object_list
        self.assertTrue(all(["Mass" in genre.mass_office for genre in genres]))

        response = self.client.get(reverse("genre-list"), {"mass_office": "Office"})
        self.assertEqual(response.status_code, 200)
        genres = response.context["paginator"].object_list
        self.assertTrue(all(["Office" in genre.mass_office for genre in genres]))

        # Empty value or anything else defaults to all genres
        response = self.client.get(reverse("genre-list"), {"mass_office": ""})
        self.assertEqual(response.status_code, 200)
        genres = response.context["paginator"].object_list
        self.assertQuerysetEqual(
            qs=genres,
            values=list(Genre.objects.all()),
            ordered=False,
            # The transform argument having the identity function is so the
            # members of
            # the list don't go through the repr() method, then we can
            # compare model objects to model objects
            transform=lambda x: x,
        )

    # TODO: maybe make a more general method to test pagination that I can apply
    # to all list views?
    def test_pagination(self):
        # To get total number of pages do a ceiling integer division
        q, r = divmod(self.number_of_genres, self.PAGE_SIZE)
        pages = q + bool(r)

        # Test all pages
        for page_num in range(1, pages + 1):
            response = self.client.get(reverse("genre-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue("is_paginated" in response.context)
            if self.number_of_genres > self.PAGE_SIZE:
                self.assertTrue(response.context["is_paginated"])
            else:
                self.assertFalse(response.context["is_paginated"])
            if page_num == pages and (self.number_of_genres % self.PAGE_SIZE != 0):
                self.assertEqual(
                    len(response.context["genres"]),
                    self.number_of_genres % self.PAGE_SIZE,
                )
            else:
                self.assertEqual(len(response.context["genres"]), self.PAGE_SIZE)

        # Test the "last" syntax
        response = self.client.get(reverse("genre-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)

        # Test some invalid values for pages
        response = self.client.get(reverse("genre-list"), {"page": -1})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("genre-list"), {"page": 0})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("genre-list"), {"page": "lst"})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("genre-list"), {"page": pages + 1})
        self.assertEqual(response.status_code, 404)


class GenreDetailViewTest(TestCase):
    fixtures = ["genre_fixtures.json"]
    SLICE_SIZE = 10

    def setUp(self):
        self.number_of_genres = Genre.objects.all().count()
        self.slice_begin = random.randint(0, self.number_of_genres - self.SLICE_SIZE)
        self.slice_end = self.slice_begin + self.SLICE_SIZE
        return super().setUp()

    def test_view_url_path(self):
        for genre in Genre.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(f"/genres/{genre.id}")
            self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        for genre in Genre.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("genre-detail", args=[genre.id]))
            self.assertEqual(response.status_code, 200)

    def test_view_correct_templates(self):
        for genre in Genre.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("genre-detail", args=[genre.id]))
            self.assertEqual(response.status_code, 200)
            self.assertTemplateUsed(response, "base.html")
            self.assertTemplateUsed(response, "genre_detail.html")

    def test_view_context_data(self):
        for genre in Genre.objects.all()[self.slice_begin : self.slice_end]:
            response = self.client.get(reverse("genre-detail", args=[genre.id]))
            self.assertTrue("genre" in response.context)
            self.assertEqual(genre, response.context["genre"])


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
