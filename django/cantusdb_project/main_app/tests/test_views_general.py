from django.urls import reverse
from django.test import TestCase

from main_app.views.feast import FeastListView
from .make_fakes import *

# run with `python -Wa manage.py test main_app.tests.test_views_genral`
# the -Wa flag tells Python to display deprecation warnings


def get_random_search_term(target):
    """Helper function for generating a random slice of a string.

    Args:
        target (str): The content of the field to search.
    
    Returns:
        str: A random slice of `target`
    """
    if len(target) <= 2:
        search_term = target
    else:
        slice_start = random.randint(0, len(target) - 2)
        slice_end = random.randint(slice_start + 2, len(target))
        search_term = target[slice_start:slice_end]
    return search_term


class IndexerListViewTest(TestCase):
    def test_url_and_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "indexer_list.html")

    def test_only_public_indexer_visible(self):
        """In the indexer list view, only public indexers (those who have at least one public source) should be visible"""
        # generate some indexers
        indexer_with_public_source = make_fake_indexer()
        indexer_with_private_source = make_fake_indexer()
        indexer_with_no_source = make_fake_indexer()

        # generate public/private sources and assign indexers to them
        private_source = Source.objects.create(title="private source", public=False)
        private_source.inventoried_by.set([indexer_with_private_source])

        public_source = Source.objects.create(title="published source", public=True)
        public_source.inventoried_by.set([indexer_with_public_source])

        source_with_multiple_indexers = Source.objects.create(
            title="private source with multiple indexers", public=False,
        )
        source_with_multiple_indexers.inventoried_by.set(
            [indexer_with_public_source, indexer_with_private_source]
        )

        # access the page context, only the public indexer should be in the context
        response = self.client.get(reverse("indexer-list"))
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])
        self.assertNotIn(indexer_with_private_source, response.context["indexers"])
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

    def test_search_first_name(self):
        """
        Indexer can be searched by passing a `q` parameter to the url \\
        Search fields include first name, family name, country, city, and institution \\
        Only public indexers should appear in the results
        """
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        # search with a random slice of first name
        target = indexer_with_public_source.first_name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])

    def test_search_family_name(self):
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        target = indexer_with_public_source.family_name
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])

    def test_search_country(self):
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        target = indexer_with_public_source.country
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])

    def test_search_city(self):
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        target = indexer_with_public_source.city
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])

    def test_search_institution(self):
        indexer_with_public_source = make_fake_indexer()
        public_source = Source.objects.create(title="published source", public=True,)
        public_source.inventoried_by.set([indexer_with_public_source])

        target = indexer_with_public_source.institution
        search_term = get_random_search_term(target)
        response = self.client.get(reverse("indexer-list"), {"q": search_term})
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])


class IndexerDetailViewTest(TestCase):
    def test_url_and_templates(self):
        """Test the url and templates used"""
        indexer = make_fake_indexer()
        response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "indexer_detail.html")

    def test_context(self):
        indexer = make_fake_indexer()
        response = self.client.get(reverse("indexer-detail", args=[indexer.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(indexer, response.context["indexer"])


class FeastListViewTest(TestCase):
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
        self.assertEqual(feasts.query.order_by[0], "name")

        # Empty ordering parameters in GET request should default to ordering by name
        response = self.client.get(reverse("feast-list"), {"sort_by": ""})
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "name")

        # Anything other than name and feast_code should default to ordering by name
        response = self.client.get(
            reverse("feast-list"), {"sort_by": make_fake_text(max_size=5)}
        )
        self.assertEqual(response.status_code, 200)
        feasts = response.context["feasts"]
        self.assertEqual(feasts.query.order_by[0], "name")

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

    def test_most_frequent_chants(self):
        source = Source.objects.create(public=True, visible=True, title="public_source")
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

    def test_sources_containing_this_feast(self):
        big_source = Source.objects.create(
            public=True, visible=True, title="big_source", siglum="big"
        )
        small_source = Source.objects.create(
            public=True, visible=True, title="small_source", siglum="small"
        )
        feast = make_fake_feast()
        # 3 chants in the big source
        for i in range(3):
            Chant.objects.create(feast=feast, source=big_source)
        # 1 chant in the small source
        Chant.objects.create(feast=feast, source=small_source)

        response = self.client.get(reverse("feast-detail", args=[feast.id]))
        sources_zip = response.context["sources_zip"]
        # the items in zip should be ordered by chant count
        # the first field is siglum
        self.assertEqual(sources_zip[0][0].siglum, "big")
        self.assertEqual(sources_zip[1][0].siglum, "small")
        # the second field is chant_count
        self.assertEqual(sources_zip[0][1], 3)
        self.assertEqual(sources_zip[1][1], 1)

