"""Leading or trailing spaces and tabs don't change search results (#2005)."""

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from main_app.models import Chant
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_segment,
    make_fake_source,
)


class SearchWhitespaceTest(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cantus = make_fake_segment(id=settings.CANTUS_SEGMENT_ID)
        make_fake_segment(id=settings.CCDB_SEGMENT_ID)
        cls.source = make_fake_source(published=True, segment=[cantus])
        chant = make_fake_chant(source=cls.source)
        Chant.objects.filter(pk=chant.pk).update(
            incipit="Alleluia laudate",
            manuscript_full_text_std_spelling="Alleluia laudate pueri",
            cantus_id="003456",
        )
        cls.chant = Chant.objects.get(pk=chant.pk)

    def found(self, url: str, params: dict) -> bool:
        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)
        return self.chant in response.context["chants"]

    def test_leading_and_trailing_whitespace_is_ignored(self) -> None:
        pages = (
            reverse("chant-search"),
            reverse("chant-search-ms", args=[self.source.id]),
        )
        for url in pages:
            for value in (" Alleluia", "\tAlleluia", "Alleluia  ", " \tAlleluia \t"):
                with self.subTest(url=url, value=repr(value)):
                    self.assertTrue(
                        self.found(url, {"keyword": value, "op": "starts_with"})
                    )
            with self.subTest(url=url, param="cantus_id"):
                self.assertTrue(self.found(url, {"cantus_id": " 003456 "}))

    def test_global_search_bar_ignores_whitespace(self) -> None:
        self.assertTrue(
            self.found(reverse("chant-search"), {"search_bar": "  Alleluia  "})
        )

    def test_search_form_shows_the_trimmed_keyword(self) -> None:
        response = self.client.get(
            reverse("chant-search"), {"keyword": "  Alleluia ", "op": "starts_with"}
        )
        self.assertEqual(response.context["keyword"], "Alleluia")
