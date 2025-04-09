"""
Test views in views/site_stats.py
"""

from django.test import TestCase
from django.urls import reverse

from main_app.tests.make_fakes import (
    make_fake_institution,
    make_fake_source,
    make_fake_chant,
)
from main_app.tests.mixins import CustomAccessTestMixin


class ContentOverviewTest(CustomAccessTestMixin, TestCase):
    default_user = "superuser"

    def test_permissions(self) -> None:
        self.client.logout()
        self.assertEqual(self.client.get(reverse("content-overview")).status_code, 302)
        self.client.force_login(user=self.users["user"])
        self.assertEqual(self.client.get(reverse("content-overview")).status_code, 403)
        self.client.force_login(user=self.users["editor"])
        self.assertEqual(self.client.get(reverse("content-overview")).status_code, 403)
        self.client.force_login(user=self.users["superuser"])
        self.assertEqual(self.client.get(reverse("content-overview")).status_code, 200)

    def test_content_overview_view_selected_model(self):
        response = self.client.get(reverse("content-overview"), {"model": "sources"})
        self.assertEqual(response.status_code, 200)

        self.assertIsNotNone(response.context["models"])
        _ = response.context["models"]
        self.assertIsNotNone(response.context["page_obj"])
        _ = response.context["page_obj"]
        self.assertEqual(response.context["selected_model_name"], "sources")

    def test_source_selected_model(self):
        hinst = make_fake_institution(name="Institution", siglum="A")
        _ = make_fake_source(shelfmark="Test Source", holding_institution=hinst)
        _ = make_fake_chant()
        response = self.client.get(reverse("content-overview"), {"model": "sources"})
        self.assertContains(response, f"<b>Sources</b>", html=True)
        self.assertContains(
            response,
            f'<a href="?model=chants">Chants</a>',
            html=True,
        )
        self.assertContains(response, "A Test Source")
        self.assertNotContains(response, "Test Chant", html=True)

    def test_chant_selected_model(self):
        source = make_fake_source(shelfmark="Test Source")
        chant = make_fake_chant(manuscript_full_text_std_spelling="Test Chant")
        response = self.client.get(reverse("content-overview"), {"model": "chants"})
        self.assertContains(response, f"<b>Chants</b>", html=True)
        self.assertContains(
            response,
            f'<a href="?model=sources">Sources</a>',
            html=True,
        )
        self.assertContains(response, "Test Chant", html=True)
        self.assertNotContains(response, "Test Source", html=True)
