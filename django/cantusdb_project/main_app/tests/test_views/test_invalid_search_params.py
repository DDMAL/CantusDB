"""
A search or filter parameter that should be an id but isn't a number, e.g.
from an edited URL, is ignored instead of causing a 500 error (#1484).
"""

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_segment,
    make_fake_source,
)


class InvalidSearchParamsTest(TestCase):
    def setUp(self) -> None:
        cantus_segment = make_fake_segment(id=settings.CANTUS_SEGMENT_ID)
        self.source = make_fake_source(published=True, segment=[cantus_segment])
        self.chant = make_fake_chant(source=self.source)

    def test_non_numeric_ids_are_ignored(self) -> None:
        source = self.source.id
        pages = [
            (reverse("browse-chants", args=[source]), ("feast", "genre")),
            (reverse("source-list"), ("segment", "provenance")),
            (reverse("chant-search"), ("genre", "service", "segment")),
            (reverse("chant-search-ms", args=[source]), ("genre", "service")),
            (reverse("melody-search"), ("source",)),
            (reverse("feast-list"), ("month",)),
        ]
        for url, params in pages:
            for param in params:
                with self.subTest(url=url, param=param):
                    response = self.client.get(url, {param: "abc"})
                    self.assertEqual(response.status_code, 200)

    def test_browse_chants_ignores_only_the_bad_filter(self) -> None:
        response = self.client.get(
            reverse("browse-chants", args=[self.source.id]),
            {"feast": "abc", "genre": self.chant.genre_id},
        )
        self.assertIn(self.chant, response.context["chants"])

    def test_melody_search_ignores_a_source_that_does_not_exist(self) -> None:
        response = self.client.get(reverse("melody-search"), {"source": "99999999"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["source"])

    def test_oldcantus_redirects_reject_a_non_numeric_source(self) -> None:
        for name in ("redirect-chants", "redirect-source-inventory"):
            with self.subTest(name=name):
                response = self.client.get(reverse(name), {"source": "abc"})
                self.assertEqual(response.status_code, 400)
                response = self.client.get(reverse(name), {"source": self.source.id})
                self.assertEqual(response.status_code, 301)
