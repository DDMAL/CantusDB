from django.test import TestCase
from latin_syllabification import (
    clean_transcript,
    syllabify_word,
)

# run with `python -Wa manage.py test main_app.tests.test_functions`
# the -Wa flag tells Python to display deprecation warnings


class LatinSyllabificationTest(TestCase):
    def test_clean_transcript(self):
        # remove all characters that are not letters or whitespace
        text_with_symbols = "!a@l#l$e%l&u*i(a)"
        cleaned_text_with_symbols = clean_transcript(text_with_symbols)
        self.assertEqual(cleaned_text_with_symbols, "alleluia")

        text_with_pipe = "puer | natus | est"
        cleaned_text_with_pipe = clean_transcript(text_with_pipe)
        self.assertEqual(cleaned_text_with_pipe, "puer natus est")

        # change all runs of consecutive spaces to single spaces
        text_with_extra_spaces = (
            "quem   vidistis    pastores     dicite      annuntiate"
        )
        cleaned_text_with_extra_spaces = clean_transcript(text_with_extra_spaces)
        self.assertEqual(
            cleaned_text_with_extra_spaces, "quem vidistis pastores dicite annuntiate"
        )

        # remove spaces at the beginning or end of text
        text_with_leading_trailing_spaces = "   hodie xpistus natus est  "
        cleaned_text_with_lt_spaces = clean_transcript(
            text_with_leading_trailing_spaces
        )
        self.assertEqual(cleaned_text_with_lt_spaces, "hodie xpistus natus est")

    def test_syllabify_word(self):
        # test special cases
        special_cases_and_expected_results = [
            ("euouae", ["e", "u", "o", "u", "ae"]),
            ("cuius", ["cu", "ius"]),
            ("eius", ["e", "ius"]),
            ("iugum", ["iu", "gum"]),
            ("iustum", ["iu", "stum"]),
            ("iusticiam", ["iu", "sti", "ci", "am"]),
            ("iohannes", ["io", "han", "nes"]),
        ]
        for word, expected_syllabification in special_cases_and_expected_results:
            self.assertEqual(syllabify_word(word), expected_syllabification)

        # test consonant_groups
        consonant_words_and_expected_results = [
            # qu
            ("quem", ["quem"]),
            ("tantaque", ["tan", "ta", "que"]),
            ("quasi", ["qua", "si"]),
            ("quidam", ["qui", "dam"]),
            ("quaeritis", ["quae", "ri", "tis"]),
            # ch
            ("nichil", ["ni", "chil"]),
            ("michi", ["mi", "chi"]),
            ("pulchritudinem", ["pul", "chri", "tu", "di", "nem"]),
            # ph
            ("prophetam", ["pro", "phe", "tam"]),
            ("triumphas", ["tri", "um", "phas"]),
            ("phylosophia", ["phy", "lo", "so", "phi", "a"]),
            # fl
            (
                "flores",
                ["flo", "res"],
            ),
            ("afflictionem", ["af", "fli", "cti", "o", "nem"]),
            # st
            ("castrorum", ["cast", "ro", "rum"]),
            ("noster", ["no", "ster"]),
            # br
            ("hebreorum", ["he", "bre", "o", "rum"]),
            ("rubrum", ["ru", "brum"]),
            # cr
            ("sacra", ["sa", "cra"]),
            ("crucis", ["cru", "cis"]),
            # cl
            ("inclita", ["in", "cli", "ta"]),
            ("declinate", ["de", "cli", "na", "te"]),
            ("claritate", ["cla", "ri", "ta", "te"]),
            # pr
            ("priusquam", ["pri", "us", "quam"]),
            # tr
            # ct
            # th
            # sp
        ]
        for word, expected_syllabification in consonant_words_and_expected_results:
            self.assertEqual(syllabify_word(word), expected_syllabification)

        # test diphthongs
        diphthong_words_and_expected_results = [
            # ae
            # au
            # ei
            # oe
            # ui
            # ya
            # ex
            # ix
            # ihe
            ("ihesus", ["ihe", "sus"]),
            ("iherusalem", ["ihe", "ru", "sa", "lem"]),
        ]
        for word, expected_syllabification in diphthong_words_and_expected_results:
            self.assertEqual(syllabify_word(word), expected_syllabification)

    def test_syllabify_text(self):
        pass
