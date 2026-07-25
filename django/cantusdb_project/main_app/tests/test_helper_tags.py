from django.conf import settings
from django.template import Context, Template, TemplateSyntaxError
from django.test import SimpleTestCase


class SegmentIdTagTest(SimpleTestCase):
    """Tests for the `segment_id` template tag in helper_tags."""

    @staticmethod
    def _render(key: str) -> str:
        template = Template("{% load helper_tags %}{% segment_id '" + key + "' %}")
        return template.render(Context({}))

    def test_returns_settings_value(self):
        cases = {
            "cantus": settings.CANTUS_SEGMENT_ID,
            "bower": settings.BOWER_SEGMENT_ID,
            "ccdb": settings.CCDB_SEGMENT_ID,
            "cantorales": settings.CANTORALES_SEGMENT_ID,
        }
        for key, expected in cases.items():
            with self.subTest(key=key):
                self.assertEqual(self._render(key), str(expected))

    def test_key_is_case_insensitive(self):
        self.assertEqual(self._render("CANTUS"), str(settings.CANTUS_SEGMENT_ID))

    def test_unknown_key_raises(self):
        with self.assertRaises(TemplateSyntaxError):
            self._render("not_a_segment")
