"""
Test views in views/feast.py
"""

from unittest import skip
import random

from django.test import TestCase
from django.urls import reverse
from django.db.models.functions import Lower

from main_app.models import Feast, Segment, Chant
from main_app.tests.make_fakes import (
    make_fake_feast,
    make_fake_source,
    make_fake_chant,
    make_fake_institution,
    make_random_string,
    get_random_search_term,
)
from main_app.views.feast import FeastListView


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
            Feast.objects.create(name=f"test_feast{i}", month=i)
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


class FeastDetailViewTest(TestCase):
    def setUp(self):
        # unless a segment is specified when a source is created, the source is automatically assigned
        # to the segment with the name "CANTUS Database" - to prevent errors, we must make sure that
        # such a segment exists
        Segment.objects.create(name="CANTUS Database")

    def test_url_and_templates(self):
        """Test the url and templates used"""
        feast = make_fake_feast()
        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "feast_detail.html")

    def test_context(self):
        feast = make_fake_feast()
        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(feast, response.context["feast"])

    @skip("Doesn't currently work with transactions and raw SQL queries")
    def test_most_frequent_chants(self):
        source = make_fake_source(published=True, shelfmark="published_source")
        feast = make_fake_feast()
        # 3 chants with cantus id: 300000
        for i in range(3):
            Chant.objects.create(feast=feast, cantus_id="300000", source=source)
        # 2 chants with cantus id: 200000
        for i in range(2):
            Chant.objects.create(feast=feast, cantus_id="200000", source=source)
        # 1 chant with cantus id: 100000
        Chant.objects.create(feast=feast, cantus_id="100000", source=source)

        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        frequent_chants_zip = response.context["frequent_chants_zip"]
        # the items in zip should be ordered by chant count
        # the first field is cantus id
        self.assertEqual(frequent_chants_zip[0][0], "300000")
        self.assertEqual(frequent_chants_zip[1][0], "200000")
        self.assertEqual(frequent_chants_zip[2][0], "100000")
        # the last field is cantus count
        self.assertEqual(frequent_chants_zip[0][-1], 3)
        self.assertEqual(frequent_chants_zip[1][-1], 2)
        self.assertEqual(frequent_chants_zip[2][-1], 1)

    @skip("Doesn't currently work with transactions and raw SQL queries")
    def test_chants_in_feast_published_vs_unpublished(self):
        feast = make_fake_feast()
        source = make_fake_source()
        chant = make_fake_chant(source=source, feast=feast)

        source.published = True
        source.save()
        response_1 = self.client.get(reverse("feast-detail", args=[feast.id]))
        frequent_chants_zip = response_1.context["frequent_chants_zip"]
        cantus_ids = [x[0] for x in frequent_chants_zip]
        self.assertIn(chant.cantus_id, cantus_ids)

        source.published = False
        source.save()
        response_1 = self.client.get(reverse("feast-detail", args=[feast.id]))
        frequent_chants_zip = response_1.context["frequent_chants_zip"]
        cantus_ids = [x[0] for x in frequent_chants_zip]
        self.assertNotIn(chant.cantus_id, cantus_ids)

    @skip("Doesn't currently work with transactions and raw SQL queries")
    def test_sources_containing_this_feast(self):
        holding_inst_b = make_fake_institution(siglum="big")
        holding_inst_s = make_fake_institution(siglum="small")
        big_source = make_fake_source(
            published=True, shelfmark="big_source", holding_institution=holding_inst_b
        )
        small_source = make_fake_source(
            published=True, shelfmark="small_source", holding_institution=holding_inst_s
        )
        feast = make_fake_feast()
        # 3 chants in the big source
        for i in range(3):
            Chant.objects.create(feast=feast, source=big_source)
        # 1 chant in the small source
        Chant.objects.create(feast=feast, source=small_source)

        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        sources = list(response.context["sources"])
        print(sources)
        # the items in zip should be ordered by chant count
        # the first field is siglum
        self.assertEqual(sources[0].siglum, "big")
        self.assertEqual(sources[1].siglum, "small")
        # the second field is chant_count
        self.assertEqual(sources[0].chant_count, 3)
        self.assertEqual(sources[1].chant_count, 1)

    @skip("Doesn't currently work with transactions and raw SQL queries")
    def test_sources_containing_feast_published_vs_unpublished(self):
        published_source = make_fake_source(
            published=True,
            shelfmark="published source",
        )
        unpublished_source = make_fake_source(published=False)
        feast = make_fake_feast()
        for _ in range(2):
            make_fake_chant(source=published_source, feast=feast)
        make_fake_chant(source=unpublished_source, feast=feast)

        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        sources = list(response.context["sources"])
        self.assertEqual(
            len(sources), 1
        )  # only item should be a duple corresponding to published_source
        self.assertEqual(sources[0].shelfmark, "published source")
        self.assertEqual(sources[0].count, 2)
