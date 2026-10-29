from django.test import Client, TestCase
from django.urls import reverse

from main_app.markdown import render_markdown
from main_app.models import Source
from main_app.tests.make_fakes import make_fake_source, make_fake_user


class MarkdownPreviewTest(TestCase):
    def setUp(self) -> None:
        self.user = make_fake_user()
        self.client.force_login(self.user)
        self.url = reverse("markdown-preview")

    def test_preview_matches_saved_description_and_does_not_modify_source(self) -> None:
        text = '**bold**\n\n1. First\n4. Fourth\n\n<img src="x" onerror="alert(1)">'
        source = make_fake_source(description=text)
        preview = self.client.post(self.url, {"text": text})
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json(), {"html": str(render_markdown(text))})
        page = self.client.get(reverse("source-detail", args=[source.pk]))
        self.assertContains(page, preview.json()["html"])
        self.assertNotIn("onerror", preview.json()["html"])
        self.assertIn("no-store", preview["Cache-Control"])
        source.refresh_from_db()
        self.assertEqual(source.description, text)

    def test_preview_does_not_need_a_source_or_editor_role(self) -> None:
        count = Source.objects.count()
        response = self.client.post(self.url, {"text": "**Unsaved**"})
        self.assertEqual(response.status_code, 200)
        self.assertIn("<strong>Unsaved</strong>", response.json()["html"])
        self.assertEqual(Source.objects.count(), count)

    def test_anonymous_request_requires_login(self) -> None:
        self.client.logout()
        response = self.client.post(self.url, {"text": "private text"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertNotIn("private text", response["Location"])

    def test_get_is_not_allowed(self) -> None:
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_csrf_is_required(self) -> None:
        client = Client(enforce_csrf_checks=True)
        client.get(reverse("login"))
        client.force_login(self.user)
        self.assertEqual(client.post(self.url, {"text": "**text**"}).status_code, 403)
        # The editor sends its form token with the preview request.
        token = client.cookies["csrftoken"].value
        response = client.post(self.url, {"text": "**text**"}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)

    def test_empty_preview(self) -> None:
        self.assertEqual(self.client.post(self.url, {"text": ""}).json(), {"html": ""})
