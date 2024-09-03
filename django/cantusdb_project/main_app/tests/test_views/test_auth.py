"""
Tests for views in views/auth.py
"""

from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model


class ChangePasswordViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="test@test.com")
        self.user.set_password("pass")
        self.user.save()
        self.client.login(email="test@test.com", password="pass")

    def test_url_and_templates(self):
        response_1 = self.client.get(reverse("change-password"))
        self.assertEqual(response_1.status_code, 200)
        self.assertTemplateUsed(response_1, "base.html")
        self.assertTemplateUsed(response_1, "registration/change_password.html")
        response_2 = self.client.get("/change-password/")
        self.assertEqual(response_2.status_code, 200)
        self.assertTemplateUsed(response_2, "base.html")
        self.assertTemplateUsed(response_2, "registration/change_password.html")

    def test_change_password(self):
        response_1 = self.client.post(
            reverse("change-password"),
            {
                "old_password": "pass",
                "new_password1": "updated_pass",
                "new_password2": "updated_pass",
            },
        )
        self.assertEqual(response_1.status_code, 200)
        self.client.logout()
        self.client.login(email="test@test.com", password="updated_pass")
        response_2 = self.client.get(reverse("change-password"))
        self.assertEqual(
            response_2.status_code, 200
        )  # if login failed, status code will be 302
