"""
Test views in views/century.py
"""

from django.test import TestCase
from django.urls import reverse
from main_app.tests.make_fakes import make_fake_century, make_fake_source
from main_app.tests.mixins import CustomAccessTestMixin


class CenturyDetailViewTest(CustomAccessTestMixin, TestCase):
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

    def test_permissions(self) -> None:
        century = make_fake_century()
        published_sources = [
            make_fake_source(century=century, published=True) for _ in range(5)
        ]
        unpublished_sources = [
            make_fake_source(century=century, published=False) for _ in range(5)
        ]
        editor_assigned_source = make_fake_source(century=century, published=False)
        editor_assigned_source.current_editors.add(self.users["editor"])
        user_assigned_source = make_fake_source(century=century, published=False)
        user_assigned_source.current_editors.add(self.users["user"])
        all_sources = (
            published_sources
            + unpublished_sources
            + [user_assigned_source, editor_assigned_source]
        )
        with self.subTest("Test superuser"):
            self.client.force_login(self.users["superuser"])
            response = self.client.get(reverse("century-detail", args=[century.id]))
            returned_sources = response.context["sources"]
            self.assertCountEqual(
                returned_sources,
                all_sources,
            )
        with self.subTest("Test global viewer"):
            self.client.force_login(self.users["global viewer"])
            response = self.client.get(reverse("century-detail", args=[century.id]))
            returned_sources = response.context["sources"]
            self.assertCountEqual(
                returned_sources,
                all_sources,
            )
        with self.subTest("Test editor"):
            self.client.force_login(self.users["editor"])
            response = self.client.get(reverse("century-detail", args=[century.id]))
            returned_sources = response.context["sources"]
            self.assertCountEqual(
                returned_sources,
                published_sources + [editor_assigned_source],
            )
        with self.subTest("Test user"):
            self.client.force_login(self.users["user"])
            response = self.client.get(reverse("century-detail", args=[century.id]))
            returned_sources = response.context["sources"]
            self.assertCountEqual(
                returned_sources,
                published_sources + [user_assigned_source],
            )
