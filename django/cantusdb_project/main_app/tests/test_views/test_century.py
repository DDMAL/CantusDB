"""
Test views in views/century.py
"""

from django.test import TestCase
from django.urls import reverse
from main_app.tests.make_fakes import make_fake_century, make_fake_source


class CenturyDetailViewTest(TestCase):
    def test_view_url_path(self):
        century = make_fake_century()
        response = self.client.get(f"/century/{century.id}")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        century = make_fake_century()
        response = self.client.get(reverse("century-detail", args=[century.id]))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        century = make_fake_century()
        response = self.client.get(reverse("century-detail", args=[century.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "century_detail.html")

    def test_listed_sources(self):
        century = make_fake_century()
        century_sources = [
            make_fake_source(century=century, published=True) for _ in range(5)
        ]
        response = self.client.get(reverse("century-detail", args=[century.id]))
        returned_sources = response.context["sources"]
        for source in century_sources:
            self.assertIn(source, returned_sources)

    def test_unpublished_sources_not_listed(self):
        century = make_fake_century()
        published_sources = [
            make_fake_source(century=century, published=True) for _ in range(5)
        ]
        unpublished_sources = [
            make_fake_source(century=century, published=False) for _ in range(5)
        ]
        response = self.client.get(reverse("century-detail", args=[century.id]))
        returned_sources = response.context["sources"]
        for source in published_sources:
            self.assertIn(source, returned_sources)
        for source in unpublished_sources:
            self.assertNotIn(source, returned_sources)
