"""
Test views in views/provenance.py
"""

from django.test import TestCase
from django.urls import reverse

from main_app.tests.make_fakes import make_fake_provenance, make_fake_source
from main_app.tests.mixins import CustomAccessTestMixin


class ProvenanceDetailViewTest(CustomAccessTestMixin, TestCase):
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

    def test_listed_sources(self) -> None:
        provenance = make_fake_provenance()
        published_sources = [
            make_fake_source(provenance=provenance, published=True) for _ in range(5)
        ]
        unpublished_sources = [
            make_fake_source(provenance=provenance, published=False) for _ in range(5)
        ]
        editor_source = make_fake_source(
            provenance=provenance,
            published=False,
            current_editors=[self.users["editor"]],
        )
        user_source = make_fake_source(
            provenance=provenance, published=False, current_editors=[self.users["user"]]
        )
        with self.subTest("Test anonymous user"):
            response = self.client.get(
                reverse("provenance-detail", args=[provenance.id])
            )
            returned_sources = response.context["sources"]
            self.assertCountEqual(published_sources, returned_sources)
        with self.subTest("Test superuser"):
            self.client.force_login(user=self.users["superuser"])
            response = self.client.get(
                reverse("provenance-detail", args=[provenance.id])
            )
            returned_sources = response.context["sources"]
            self.assertCountEqual(
                published_sources + unpublished_sources + [editor_source, user_source],
                returned_sources,
            )
            self.client.logout()
        with self.subTest("Test global viewer"):
            self.client.force_login(user=self.users["global viewer"])
            response = self.client.get(
                reverse("provenance-detail", args=[provenance.id])
            )
            returned_sources = response.context["sources"]
            self.assertCountEqual(
                published_sources + unpublished_sources + [editor_source, user_source],
                returned_sources,
            )
            self.client.logout()
        with self.subTest("Test assigned editor"):
            self.client.force_login(user=self.users["editor"])
            response = self.client.get(
                reverse("provenance-detail", args=[provenance.id])
            )
            returned_sources = response.context["sources"]
            self.assertCountEqual(published_sources + [editor_source], returned_sources)
            self.client.logout()
        with self.subTest("Test assigned user"):
            self.client.force_login(user=self.users["user"])
            response = self.client.get(
                reverse("provenance-detail", args=[provenance.id])
            )
            returned_sources = response.context["sources"]
            self.assertCountEqual(published_sources + [user_source], returned_sources)
            self.client.logout()
