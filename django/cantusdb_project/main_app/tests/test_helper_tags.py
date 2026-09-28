from django.conf import settings
from django.template import Context, Template, TemplateSyntaxError
from django.test import SimpleTestCase, override_settings
from volpiano_display_utilities.text_volpiano_alignment import align_text_and_volpiano

from main_app.templatetags.helper_tags import split_missing_music


class SplitMissingMusicTest(SimpleTestCase):
    def test_preserves_whitespace_and_staff_boundary_markers(self) -> None:
        text = "{Fidelium  deus\ttuo}"
        melody = "6" + "-" * len(text) + "67---"
        pieces = split_missing_music([(text, melody)])
        self.assertEqual([t for t, _ in pieces], ["{Fidelium  ", "deus\t", "tuo}"])
        self.assertEqual("".join(t for t, _ in pieces), text)
        self.assertEqual("".join(m for _, m in pieces), melody)
        self.assertTrue(pieces[0][1].startswith("6"))
        self.assertTrue(pieces[-1][1].endswith("67---"))
        self.assertEqual(set(pieces[1][1]), {"-"})

    def test_notated_and_single_word_sections_remain_intact(self) -> None:
        alignment = [
            ("", "1---"),
            ("Al-", "f--"),
            ("|", "3---"),
            ("{Amen}", "6------6---"),
            ("{text with notes}", "6---f---6---"),
            ("unsyllabified text", "f---g---"),
            ("", "6------6---"),
            ("", "4"),
        ]
        self.assertEqual(split_missing_music(alignment), alignment)

    def test_empty_alignment(self) -> None:
        self.assertEqual(split_missing_music(None), [])
        self.assertEqual(split_missing_music([]), [])

    def test_short_passages_keep_their_fixed_width_staff(self) -> None:
        for text in ("{A b}", "{Tu autem}", "{Ab cdefg}"):
            with self.subTest(text=text):
                alignment, _ = align_text_and_volpiano(text, "1---6------6---4")
                self.assertEqual(split_missing_music(alignment), alignment)

    def test_barlines_immediately_after_missing_music_remain_separate(self) -> None:
        missing_text = "{Fidelium deus omnium conditor et redemptor}"
        for text, melody, barline in [
            (missing_text + " | Amen", "1---6------63---f--g---4", ("|", "3---")),
            (missing_text, "1---6------64", ("", "4")),
        ]:
            with self.subTest(melody=melody):
                alignment, _ = align_text_and_volpiano(text, melody)
                pieces = split_missing_music(alignment)
                self.assertIn("{Fidelium ", [t for t, _ in pieces])
                self.assertIn(barline, pieces)
                self.assertEqual(
                    "".join(t for t, _ in pieces), "".join(t for t, _ in alignment)
                )
                self.assertEqual(
                    "".join(m for _, m in pieces), "".join(m for _, m in alignment)
                )

    def test_library_alignment_keeps_text_and_music_with_saved_syllabification(
        self,
    ) -> None:
        for presyllabified, text in [
            (False, "Amen {et cum spiritu tuo} Amen"),
            (True, "A-men {et cum spi-ri-tu tuo} A-men"),
        ]:
            with self.subTest(presyllabified=presyllabified):
                alignment, _ = align_text_and_volpiano(
                    text,
                    "1---f--g---6------67---g--f---4",
                    text_presyllabified=presyllabified,
                )
                pieces = split_missing_music(alignment)
                self.assertIn("{et ", [t for t, _ in pieces])
                self.assertIn("cum ", [t for t, _ in pieces])
                self.assertEqual(
                    "".join(t for t, _ in pieces), "".join(t for t, _ in alignment)
                )
                self.assertEqual(
                    "".join(m for _, m in pieces), "".join(m for _, m in alignment)
                )
                for pair in alignment:
                    if not pair[1].startswith("6"):
                        self.assertIn(pair, pieces)

    def test_split_text_is_escaped_when_rendered(self) -> None:
        template = Template(
            "{% load helper_tags %}"
            "{% for text, melody in alignment|split_missing_music %}"
            "{{ text }}{% endfor %}"
        )
        rendered = template.render(
            Context({"alignment": [("{<b> et}", "6----------6---")]})
        )
        self.assertEqual(rendered, "{&lt;b&gt; et}")


class SegmentIdTagTest(SimpleTestCase):
    """Tests for the `segment_id` template tag in helper_tags."""

    @staticmethod
    def _render(key: str) -> str:
        template = Template("{% load helper_tags %}{% segment_id '" + key + "' %}")
        return template.render(Context({}))

    def test_returns_settings_value(self) -> None:
        cases = {
            "cantus": settings.CANTUS_SEGMENT_ID,
            "bower": settings.BOWER_SEGMENT_ID,
            "ccdb": settings.CCDB_SEGMENT_ID,
            "cantorales": settings.CANTORALES_SEGMENT_ID,
        }
        for key, expected in cases.items():
            with self.subTest(key=key):
                self.assertEqual(self._render(key), str(expected))

    @override_settings(
        CANTUS_SEGMENT_ID=9063,
        BOWER_SEGMENT_ID=9064,
        CCDB_SEGMENT_ID=9066,
        CANTORALES_SEGMENT_ID=9067,
    )
    def test_returns_overridden_settings(self) -> None:
        self.test_returns_settings_value()

    def test_key_is_case_insensitive(self) -> None:
        self.assertEqual(self._render("CANTUS"), str(settings.CANTUS_SEGMENT_ID))

    def test_unknown_key_raises(self) -> None:
        with self.assertRaises(TemplateSyntaxError):
            self._render("not_a_segment")
