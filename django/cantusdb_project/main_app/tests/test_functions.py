from django.test import TestCase
from typing import Union
from main_app.models import (
    Chant,
    Source,
)
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_source,
)
from main_app.management.commands import update_cached_concordances

# run with `python -Wa manage.py test main_app.tests.test_functions`
# the -Wa flag tells Python to display deprecation warnings


class UpdateCachedConcordancesCommandTest(TestCase):
    def test_concordances_structure(self):
        chant: Chant = make_fake_chant(cantus_id="123456")
        concordances: dict = update_cached_concordances.get_concordances()

        with self.subTest(test="Ensure get_concordances returns dict"):
            self.assertIsInstance(concordances, dict)

        concordances_for_single_cantus_id: list = concordances["123456"]
        with self.subTest(test="Ensure values are lists"):
            self.assertIsInstance(concordances_for_single_cantus_id, list)

        single_concordance = concordances_for_single_cantus_id[0]
        with self.subTest(test="Ensure each concordance is a dict"):
            single_concordance: dict = concordances_for_single_cantus_id[0]
            self.assertIsInstance(single_concordance, dict)

        expected_keys = (
            "siglum",
            "srclink",
            "chantlink",
            "folio",
            "sequence",
            "incipit",
            "feast",
            "genre",
            "office",
            "position",
            "cantus_id",
            "image",
            "mode",
            "full_text",
            "melody",
            "db",
        )
        concordance_keys = single_concordance.keys()
        for key in expected_keys:
            with self.subTest(key=key):
                self.assertIn(key, concordance_keys)
        with self.subTest(test="Ensure no unexpected keys present"):
            self.assertEqual(len(concordance_keys), len(expected_keys))

    def test_number_of_concordances_returned(self):
        cantus_ids: tuple[tuple[str, int]] = (
            ("000002", 2),
            ("000003", 3),
            ("000005", 5),
            ("000007", 7),
            ("000011", 11),
        )
        for cantus_id, n in cantus_ids:
            for _ in range(n):
                make_fake_chant(cantus_id=cantus_id)

        concordances: dict = update_cached_concordances.get_concordances()
        with self.subTest(test="Test all Cantus IDs present"):
            self.assertEqual(len(concordances), len(cantus_ids))

        for cantus_id, n in cantus_ids:
            concordances_for_id: list = concordances[cantus_id]
            with self.subTest(n=n):
                self.assertEqual(len(concordances_for_id), n)

    def test_published_vs_unpublished(self):
        published_source: Source = make_fake_source(published=True)
        published_chant: Chant = make_fake_chant(
            source=published_source,
            cantus_id="123456",
            incipit="chant in a published source",
        )
        unpublished_source: Source = make_fake_source(published=False)
        unpublished_chant: Chant = make_fake_chant(
            source=unpublished_source,
            cantus_id="123456",
            incipit="chant in an unpublished source",
        )

        concordances: dict = update_cached_concordances.get_concordances()
        concordances_for_single_id: list = concordances["123456"]
        self.assertEqual(len(concordances), 1)

        single_concordance: dict = concordances_for_single_id[0]
        expected_incipit: str = published_chant.incipit
        observed_incipit: str = single_concordance["incipit"]
        self.assertEqual(expected_incipit, observed_incipit)

    def test_concordances_values(self):
        chant: Chant = make_fake_chant()
        cantus_id: str = chant.cantus_id

        concordances: dict = update_cached_concordances.get_concordances()
        concordances_for_single_id: list = concordances[cantus_id]
        single_concordance: dict = concordances_for_single_id[0]

        expected_items: tuple = (
            ("siglum", chant.source.siglum),
            ("srclink", f"https://cantusdatabase.org/source/{chant.source.id}/"),
            ("chantlink", f"https://cantusdatabase.org/chant/{chant.id}/"),
            ("folio", chant.folio),
            ("sequence", chant.c_sequence),
            ("incipit", chant.incipit),
            ("feast", chant.feast.name),
            ("genre", chant.genre.name),
            ("office", chant.office.name),
            ("position", chant.position),
            ("cantus_id", chant.cantus_id),
            ("image", chant.image_link),
            ("mode", chant.mode),
            ("full_text", chant.manuscript_full_text_std_spelling),
            ("melody", chant.volpiano),
            ("db", "CD"),
        )

        for key, value in expected_items:
            observed_value: Union[str, int, None] = single_concordance[key]
            with self.subTest(key=key):
                self.assertEqual(observed_value, value)
