from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_segment,
    make_fake_source,
)

# HTML typed into a source's name, summary or indexing notes must reach the
# page as text, not as markup (#2383).
MARKUP = '<img src="x" data-test="escaped">'
ESCAPED = "&lt;img src=&quot;x&quot; data-test=&quot;escaped&quot;&gt;"


class SourceFieldEscapingTest(TestCase):
    def make_source(self, segment_id=None):
        source = make_fake_source(
            published=True, name=MARKUP, summary=MARKUP, indexing_notes=MARKUP
        )
        if segment_id is not None:
            source.segment_m2m.set([make_fake_segment(id=segment_id)])
        return source

    def assert_escaped(self, url, minimum):
        html = self.client.get(url).content.decode()
        self.assertNotIn(MARKUP, html)
        self.assertGreaterEqual(html.count(ESCAPED), minimum)

    def test_source_list(self):
        self.make_source()
        # name, and the summary twice (title and text)
        self.assert_escaped(reverse("source-list"), 3)

    def test_canadian_chant_db_lists(self):
        self.make_source(settings.CCDB_SEGMENT_ID)
        for name in ("canadian-chant-db-source-list", "ccdb-browse"):
            with self.subTest(page=name):
                self.assert_escaped(reverse(name), 3)

    def test_cantorales_list(self):
        self.make_source(settings.CANTORALES_SEGMENT_ID)
        self.assert_escaped(reverse("cantorales-source-list"), 3)

    def test_source_page(self):
        source = self.make_source()
        self.assert_escaped(reverse("source-detail", args=[source.id]), 2)

    def test_chant_page(self):
        chant = make_fake_chant(source=self.make_source())
        self.assert_escaped(reverse("chant-detail", args=[chant.id]), 1)
