from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse


class SelfHostedFontTest(TestCase):
    """Radio Canada is served from our own static files, never from Google's CDN.

    The font is the fix for sigla like D-WI1, where a fallback face renders "1" and
    uppercase "I" identically. Fetching it from fonts.googleapis.com makes the fix
    depend on a third party being reachable, so these guard against a reversion.
    """

    def test_page_loads_the_font_from_our_own_static_files(self) -> None:
        response = self.client.get(reverse("article-list"))
        self.assertContains(response, "fonts/radio-canada.css")

    def test_no_template_references_google_fonts(self) -> None:
        base_dir = Path(settings.BASE_DIR)
        templates = sorted(base_dir.glob("**/templates/**/*.html"))
        self.assertGreater(len(templates), 0, "found no templates to check")
        for template in templates:
            with self.subTest(template=str(template.relative_to(base_dir))):
                source = template.read_text(encoding="utf-8")
                self.assertNotIn("fonts.googleapis.com", source)
                self.assertNotIn("fonts.gstatic.com", source)
