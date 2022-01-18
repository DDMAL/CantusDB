from django.urls import reverse
from django.test import TestCase
from main_app.models import Indexer, Source, indexer
from .make_fakes import *

# python manage.py test main_app.tests.test_views.IndexerListViewTest
# display deprecation warnings during testing: python -Wa manage.py test


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

        public_source = Source.objects.create(
            title="published source",
            public=True,
        )
        public_source.inventoried_by.set([indexer_with_public_source])

        source_with_multiple_indexers = Source.objects.create(
            title="private source with multiple indexers",
            public=False,
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

    def test_search_indexer(self):
        """
        Indexer can be searched by passing a `q` parameter to the url \\
        Search fields include first name, family name, country, city, and institution \\
        Only public indexers should appear in the results
        """
        # generate some indexers
        indexer_with_public_source = make_fake_indexer()
        indexer_with_private_source = make_fake_indexer()
        indexer_with_no_source = make_fake_indexer()

        # generate public/private sources and assign indexers to them
        private_source = Source.objects.create(title="private source", public=False)
        private_source.inventoried_by.set([indexer_with_private_source])

        public_source = Source.objects.create(
            title="published source",
            public=True,
        )
        public_source.inventoried_by.set([indexer_with_public_source])

        source_with_multiple_indexers = Source.objects.create(
            title="private source with multiple indexers",
            public=False,
        )
        source_with_multiple_indexers.inventoried_by.set(
            [indexer_with_public_source, indexer_with_private_source]
        )

        # search for the public indexer
        response = self.client.get(
            reverse("indexer-list"), {"q": indexer_with_public_source.first_name}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])
        self.assertNotIn(indexer_with_private_source, response.context["indexers"])
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

        response = self.client.get(
            reverse("indexer-list"), {"q": indexer_with_public_source.family_name}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])
        self.assertNotIn(indexer_with_private_source, response.context["indexers"])
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

        response = self.client.get(
            reverse("indexer-list"), {"q": indexer_with_public_source.institution}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])
        self.assertNotIn(indexer_with_private_source, response.context["indexers"])
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

        response = self.client.get(
            reverse("indexer-list"), {"q": indexer_with_public_source.country}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])
        self.assertNotIn(indexer_with_private_source, response.context["indexers"])
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

        response = self.client.get(
            reverse("indexer-list"), {"q": indexer_with_public_source.city}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])
        self.assertNotIn(indexer_with_private_source, response.context["indexers"])
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

        # search for the private indexer
        response = self.client.get(
            reverse("indexer-list"), {"q": indexer_with_private_source.first_name}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(indexer_with_private_source, response.context["indexers"])

        # search for the no-source indexer
        response = self.client.get(
            reverse("indexer-list"), {"q": indexer_with_no_source.first_name}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(indexer_with_no_source, response.context["indexers"])

        # search for a slice of the first name
        response = self.client.get(
            reverse("indexer-list"), {"q": indexer_with_public_source.first_name[:2]}
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(indexer_with_public_source, response.context["indexers"])
        # use `repr` because `asserQuerysetEqual` will transform every entry in Queryset
        # and then compare it to the corresponding item in Values, `repr` is the default transform
        self.assertQuerysetEqual(
            response.context["indexers"], [repr(indexer_with_public_source)]
        )


class IndexerDetailViewTest(TestCase):
    def test_url_templates(self):
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
    def test_url_templates(self):
        """Test the url and templates used"""
        response = self.client.get(reverse("feast-list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "feast_list.html")

    def test_search_feast(self):
        """Feast can be searched by any part of its name, description, or feastcode"""
        feast = make_fake_feast()
        response = self.client.get(reverse("feast-list"))
        pass
