from django.conf import settings
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from main_app.markdown import sanitize_html
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_segment,
    make_fake_source,
)

# HTML typed into a source's name or summary must reach the page as text, not
# as markup. Indexing notes may hold links (#1486), so they are cleaned rather
# than escaped: safe links stay, anything that could run is removed (#2383).
MARKUP = '<img src="x" data-test="escaped">'
ESCAPED = "&lt;img src=&quot;x&quot; data-test=&quot;escaped&quot;&gt;"
NOTES = (
    'See <a href="https://example.org/catalogue">the catalogue</a>.'
    "<script>probe_script()</script>"
    '<img src="x" onerror="probe_onerror()">'
    '<a href="javascript:probe_js()">bad link</a>'
)
# each unsafe piece carries a marker that must not reach the page
UNSAFE = ("probe_script", "probe_onerror", "probe_js")


class SanitizeHtmlTest(SimpleTestCase):
    def test_keeps_links_and_removes_what_could_run(self):
        cleaned = sanitize_html(NOTES)
        self.assertIn('href="https://example.org/catalogue"', cleaned)
        self.assertIn("the catalogue</a>", cleaned)
        self.assertIn("bad link", cleaned, "the text of an unsafe link stays")
        for unsafe in UNSAFE:
            self.assertNotIn(unsafe, cleaned)

    def test_plain_text_is_escaped(self):
        self.assertEqual(sanitize_html("a < b & c"), "a &lt; b &amp; c")

    def test_empty(self):
        self.assertEqual(sanitize_html(None), "")
        self.assertEqual(sanitize_html(""), "")


class SourceFieldEscapingTest(TestCase):
    def make_source(self, segment_id=None):
        source = make_fake_source(
            published=True, name=MARKUP, summary=MARKUP, indexing_notes=NOTES
        )
        if segment_id is not None:
            source.segment_m2m.set([make_fake_segment(id=segment_id)])
        return source

    def get(self, url):
        return self.client.get(url).content.decode()

    def assert_name_and_summary_escaped(self, url):
        html = self.get(url)
        self.assertNotIn(MARKUP, html)
        # name, and the summary twice (title and text)
        self.assertGreaterEqual(html.count(ESCAPED), 3)

    def assert_notes_cleaned(self, url, times):
        html = self.get(url)
        self.assertEqual(
            html.count('href="https://example.org/catalogue"'), times, "link kept"
        )
        for unsafe in UNSAFE:
            self.assertNotIn(unsafe, html)

    def test_source_list(self):
        self.make_source()
        self.assert_name_and_summary_escaped(reverse("source-list"))

    def test_canadian_chant_db_lists(self):
        self.make_source(settings.CCDB_SEGMENT_ID)
        for name in ("canadian-chant-db-source-list", "ccdb-browse"):
            with self.subTest(page=name):
                self.assert_name_and_summary_escaped(reverse(name))

    def test_cantorales_list(self):
        self.make_source(settings.CANTORALES_SEGMENT_ID)
        self.assert_name_and_summary_escaped(reverse("cantorales-source-list"))

    def test_source_page(self):
        source = self.make_source()
        self.assert_notes_cleaned(reverse("source-detail", args=[source.id]), 2)

    def test_chant_page(self):
        chant = make_fake_chant(source=self.make_source())
        self.assert_notes_cleaned(reverse("chant-detail", args=[chant.id]), 1)
