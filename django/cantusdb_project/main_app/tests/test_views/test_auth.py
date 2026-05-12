"""
Tests for views in views/auth.py
"""

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
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


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class PasswordResetViewsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create(email="reset@test.com")
        self.user.set_password("oldpass")
        self.user.save()

    def test_reset_password_form_renders(self):
        response = self.client.get(reverse("reset_password"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/reset_password.html")

    def test_reset_password_sends_email(self):
        response = self.client.post(
            reverse("reset_password"), {"email": "reset@test.com"}
        )
        self.assertRedirects(response, "/reset-password-sent/")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("reset", mail.outbox[0].subject.lower())
        self.assertIn("reset@test.com", mail.outbox[0].to)

    def test_reset_password_confirm_completes(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)

        # Django redirects to …/set-password/ on valid token; follow to land there
        confirm_response = self.client.get(
            reverse("reset_password_confirm", kwargs={"uidb64": uid, "token": token}),
            follow=True,
        )
        self.assertEqual(confirm_response.status_code, 200)

        set_password_url = confirm_response.wsgi_request.path
        post_response = self.client.post(
            set_password_url,
            {"new_password1": "newpass123!", "new_password2": "newpass123!"},
        )
        self.assertRedirects(post_response, "/reset-password-complete/")

        self.assertTrue(
            self.client.login(email="reset@test.com", password="newpass123!")
        )
        self.assertFalse(self.client.login(email="reset@test.com", password="oldpass"))

    def test_reset_password_invalid_token(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        response = self.client.get(
            reverse(
                "reset_password_confirm",
                kwargs={"uidb64": uid, "token": "invalid-token"},
            ),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context.get("validlink", False))
