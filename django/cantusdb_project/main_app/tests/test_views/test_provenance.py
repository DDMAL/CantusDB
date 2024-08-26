"""
Test views in views/provenance.py
"""

from django.test import TestCase
from django.urls import reverse

from main_app.tests.make_fakes import make_fake_provenance, make_fake_source


class ProvenanceDetailViewTest(TestCase):
    def test_view_url_path(self):
        provenance = make_fake_provenance()
        response = self.client.get(f"/provenance/{provenance.id}")
        self.assertEqual(response.status_code, 200)

    def test_view_url_reverse_name(self):
        provenance = make_fake_provenance()
        response = self.client.get(reverse("provenance-detail", args=[provenance.id]))
        self.assertEqual(response.status_code, 200)

    def test_url_and_templates(self):
        provenance = make_fake_provenance()
        response = self.client.get(reverse("provenance-detail", args=[provenance.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "provenance_detail.html")

    def test_listed_sources(self):
        provenance = make_fake_provenance()
        provenance_sources = [
            make_fake_source(provenance=provenance, published=True) for _ in range(5)
        ]
        response = self.client.get(reverse("provenance-detail", args=[provenance.id]))
        returned_sources = response.context["sources"]
        for source in provenance_sources:
            self.assertIn(source, returned_sources)

    def test_unpublished_sources_not_listed(self):
        provenance = make_fake_provenance()
        published_sources = [
            make_fake_source(provenance=provenance, published=True) for _ in range(5)
        ]
        unpublished_sources = [
            make_fake_source(provenance=provenance, published=False) for _ in range(5)
        ]
        response = self.client.get(reverse("provenance-detail", args=[provenance.id]))
        returned_sources = response.context["sources"]
        for source in published_sources:
            self.assertIn(source, returned_sources)
        for source in unpublished_sources:
            self.assertNotIn(source, returned_sources)
