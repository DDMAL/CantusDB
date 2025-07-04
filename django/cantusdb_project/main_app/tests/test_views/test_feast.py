"""
Test views in views/feast.py
"""

import random
from typing import Dict, Any

from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.db.models.functions import Lower
from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest

from main_app.tests.make_fakes import (
    make_fake_feast,
    make_fake_source,
    make_fake_chant,
    make_fake_institution,
    make_random_string,
    get_random_search_term,
)
from main_app.tests.mixins import CustomAccessTestMixin
from main_app.views.feast import FeastListView, FeastDetailView
from main_app.models import Feast, Source


class FeastListViewTest(TestCase):
    def test_view_url_path(self):
        response = self.client.get("/feasts/")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        response = self.client.get(reverse("feast-list"))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("feast-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "feast_list.html")

    def test_filter_by_month(self):
        for i in range(1, 13):
            make_fake_feast(name=f"test_feast{i}", month=i)
        for i in range(1, 13):
            month = str(i)
            response = self.client.get(reverse("feast-list"), {"month": month})
            self.assertEqual(response.status_code, 200)
            feasts = response.context["feasts"]
            self.assertTrue(all(feast.month == i for feast in feasts))

    def test_ordering(self):
        """Feast can be ordered by name or feast_code"""
        # Order by feast_code
        response = self.client.get(reverse("feast-list"), {"sort_by": "feast_code"})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "feast_code")

        # Order by name
        response = self.client.get(reverse("feast-list"), {"sort_by": "name"})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], Lower("name"))

        # Empty ordering parameters in GET request should default to ordering by name
        response = self.client.get(reverse("feast-list"), {"sort_by": ""})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], Lower("name"))

        # Anything other than name and feast_code should default to ordering by name
        response = self.client.get(
            reverse("feast-list"), {"sort_by": make_random_string(4)}
        )
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], Lower("name"))

    def test_search_name(self):
        """Feast can be searched by any part of its name, description, or feast_code"""
        feast = make_fake_feast()
        target = feast.name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("feast-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(feast, response.context["feasts"])

    def test_search_description(self):
        feast = make_fake_feast()
        target = feast.description
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("feast-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(feast, response.context["feasts"])

    def test_search_feast_code(self):
        feast = make_fake_feast()
        target = feast.feast_code
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("feast-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(feast, response.context["feasts"])

    def test_pagination(self):
        PAGINATE_BY = FeastListView.paginate_by
        # test 2 full pages of feasts
        feast_count = PAGINATE_BY * 2
        for i in range(feast_count):
            make_fake_feast()
        page_count = int(feast_count / PAGINATE_BY)
        assert page_count == 2
        for page_num in range(1, page_count + 1):
            response = self.client.get(reverse("feast-list"), {"page": page_num})
            self.assertEqual(response.status_code, 200)
            self.assertTrue("is_paginated" in response.context)
            self.assertTrue(response.context["is_paginated"])
            self.assertEqual(len(response.context["feasts"]), PAGINATE_BY)

        # test a little more than 2 full pages of feasts
        new_feast_count = feast_count + random.randint(1, PAGINATE_BY - 1)
        for i in range(new_feast_count - feast_count):
            make_fake_feast()
        new_page_count = page_count + 1
        # The last page should have the same number of feasts as we added
        response = self.client.get(reverse("feast-list"), {"page": new_page_count})
        self.assertEqual(response.status_code, 200)
        self.assertTrue("is_paginated" in response.context)
        self.assertTrue(response.context["is_paginated"])
        self.assertEqual(len(response.context["feasts"]), new_feast_count - feast_count)

        # test the "last" syntax
        response = self.client.get(reverse("feast-list"), {"page": "last"})
        self.assertEqual(response.status_code, 200)

        # Test some invalid values for pages
        response = self.client.get(reverse("feast-list"), {"page": -1})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": 0})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": "lst"})
        self.assertEqual(response.status_code, 404)
        response = self.client.get(reverse("feast-list"), {"page": new_page_count + 1})
        self.assertEqual(response.status_code, 404)


class FeastDetailViewTest(CustomAccessTestMixin, TestCase):
    test_get_allowed = False
    view_name = "feast-detail"
    feast: Feast
    factory: RequestFactory
    published_source: Source
    unpublished_source: Source
    assigned_source: Source
    request: HttpRequest

    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.factory = RequestFactory()
        cls.feast = make_fake_feast()
        cls.published_source = make_fake_source(
            published=True, shelfmark="published_source"
        )
        cls.unpublished_source = make_fake_source(
            published=False, shelfmark="unpublished_source"
        )
        cls.assigned_source = make_fake_source(
            published=False, shelfmark="assigned_source"
        )
        cls.assigned_source.current_editors.add(cls.users["editor"])
        cls.assigned_source.current_editors.add(cls.users["user"])
        cls.request = cls.factory.get(reverse("feast-detail", args=[cls.feast.id]))

    def _get_view_context(self, request: HttpRequest) -> Dict[str, Any]:
        """
        Get the context of the view. We use a RequestFactory to access
        the view's get_context_data method directly. This is to prevent the
        rendering of the template, which exhausts the generators of frequent
        chants and sources before they can be tested.
        """
        view = FeastDetailView()
        view.setup(request, pk=self.feast.id)
        view.user = request.user
        view.object = view.get_object()
        return view.get_context_data()

    def test_url_and_templates(self) -> None:
        """Test the url and templates used"""
        response = self.client.get(reverse("feast-detail", args=[self.feast.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "feast_detail.html")

    def test_context(self) -> None:
        response = self.client.get(reverse("feast-detail", args=[self.feast.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.feast, response.context["feast"])

    def test_most_frequent_chants(self) -> None:
        # 3 chants with cantus id: 300000
        for _ in range(3):
            make_fake_chant(
                feast=self.feast, cantus_id="300000", source=self.published_source
            )
        # 2 chants with cantus id: 200000
        for _ in range(2):
            make_fake_chant(
                feast=self.feast, cantus_id="200000", source=self.published_source
            )
        # 1 chant with cantus id: 100000
        make_fake_chant(
            feast=self.feast, cantus_id="100000", source=self.published_source
        )

        request = self.request
        request.user = AnonymousUser()
        context = self._get_view_context(request)
        frequent_chants = context["frequent_chants"]

        expected_chants = [
            ("300000", 3),
            ("200000", 2),
            ("100000", 1),
        ]

        for i, result_tuple in enumerate(frequent_chants):
            self.assertEqual(getattr(result_tuple, "cantus_id"), expected_chants[i][0])
            self.assertEqual(getattr(result_tuple, "ccount"), expected_chants[i][1])

    def test_sources_containing_this_feast(self) -> None:
        holding_inst_b = make_fake_institution(siglum="big")
        holding_inst_s = make_fake_institution(siglum="small")
        big_source = make_fake_source(
            published=True, shelfmark="big_source", holding_institution=holding_inst_b
        )
        small_source = make_fake_source(
            published=True, shelfmark="small_source", holding_institution=holding_inst_s
        )
        # 3 chants in the big source
        for _ in range(3):
            make_fake_chant(feast=self.feast, source=big_source)
        # 1 chant in the small source
        make_fake_chant(feast=self.feast, source=small_source)
        request = self.request
        request.user = AnonymousUser()
        context = self._get_view_context(request)
        sources = list(context["sources"])

        self.assertEqual(sources[0].siglum, "big")
        self.assertEqual(sources[1].siglum, "small")
        # the second field is chant_count
        self.assertEqual(sources[0].chant_count, 3)
        self.assertEqual(sources[1].chant_count, 1)

    def test_permissions(self) -> None:
        make_fake_chant(
            feast=self.feast, source=self.published_source, cantus_id="100000"
        )
        make_fake_chant(
            feast=self.feast, source=self.unpublished_source, cantus_id="200000"
        )
        make_fake_chant(
            feast=self.feast, source=self.assigned_source, cantus_id="300000"
        )
        with self.subTest("Test superuser"):
            request = self.request
            request.user = self.users["superuser"]
            context = self._get_view_context(request)
            frequent_chants = list(context["frequent_chants"])
            freq_chant_cantus_ids = [chant.cantus_id for chant in frequent_chants]
            self.assertCountEqual(["100000", "200000", "300000"], freq_chant_cantus_ids)
            sources = list(context["sources"])
            sources_shelfmarks = [source.shelfmark for source in sources]
            self.assertCountEqual(
                ["published_source", "unpublished_source", "assigned_source"],
                sources_shelfmarks,
            )

        with self.subTest("Test global viewer"):
            request = self.request
            request.user = self.users["global viewer"]
            context = self._get_view_context(request)
            frequent_chants = list(context["frequent_chants"])
            freq_chant_cantus_ids = [chant.cantus_id for chant in frequent_chants]
            self.assertCountEqual(["100000", "200000", "300000"], freq_chant_cantus_ids)
            sources = list(context["sources"])
            sources_shelfmarks = [source.shelfmark for source in sources]
            self.assertCountEqual(
                ["published_source", "unpublished_source", "assigned_source"],
                sources_shelfmarks,
            )
        with self.subTest("Test editor"):
            request = self.request
            request.user = self.users["editor"]
            context = self._get_view_context(request)
            frequent_chants = list(context["frequent_chants"])
            freq_chant_cantus_ids = [chant.cantus_id for chant in frequent_chants]
            self.assertCountEqual(["100000", "300000"], freq_chant_cantus_ids)
            sources = list(context["sources"])
            sources_shelfmarks = [source.shelfmark for source in sources]
            self.assertCountEqual(
                ["published_source", "assigned_source"],
                sources_shelfmarks,
            )
        with self.subTest("Test user"):
            request = self.request
            request.user = self.users["user"]
            context = self._get_view_context(request)
            frequent_chants = list(context["frequent_chants"])
            freq_chant_cantus_ids = [chant.cantus_id for chant in frequent_chants]
            self.assertCountEqual(["100000", "300000"], freq_chant_cantus_ids)
            sources = list(context["sources"])
            sources_shelfmarks = [source.shelfmark for source in sources]
            self.assertCountEqual(
                ["published_source", "assigned_source"],
                sources_shelfmarks,
            )
