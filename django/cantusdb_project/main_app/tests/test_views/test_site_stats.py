"""
Test views in views/site_stats.py
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from main_app.tests.make_fakes import (
    make_fake_institution,
    make_fake_source,
    make_fake_chant,
)


class ContentOverviewTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.create(name="project manager")

    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client = Client()

        project_manager = Group.objects.get(name="project manager")
        project_manager.user_set.add(self.user)
        self.client.login(email="test@test.com", password="pass")

    def test_templates_used(self):
        response = self.client.get(reverse("content-overview"))
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "content_overview.html")

    def test_project_manager_permission(self):
        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 200)

    def test_content_overview_view_with_login_required(self):
        self.client.logout()
        response = self.client.get(reverse("content-overview"))
        self.assertRedirects(response, "/login/?next=/content-overview/")

    def test_content_overview_view_for_non_project_manager(self):
        user = get_user_model().objects.create(email="non_project_manager@test.com")
        user.set_password("pass")
        user.save()
        self.client.login(email="non_project_manager@test.com", password="pass")

        response = self.client.get(reverse("content-overview"))
        self.assertEqual(response.status_code, 403)

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
