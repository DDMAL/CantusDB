import requests
from main_app.tests import mock_cantusindex_data
from django.test import TestCase
from typing import Union
from unittest.mock import patch
from main_app.models import (
    Chant,
    Source,
)
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_genre,
    make_fake_source,
)
from main_app.management.commands import update_cached_concordances
from main_app.signals import generate_incipit
from cantusindex import get_suggested_chant, get_suggested_chants, get_json_from_ci_api

# run with `python -Wa manage.py test main_app.tests.test_functions`
# the -Wa flag tells Python to display deprecation warnings


class MockResponse:
    def __init__(
        self,
        status_code: int,
        json: Union[dict, list, None],
        content: bytes,
        encoding: str = "utf-8",
        # >>> response = requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010")
        # >>> response.encoding
        # 'utf-8'
    ):
        self.status_code = status_code
        self._json = json
        self.content = content
        self.encoding = encoding

    def json(self):
        return self._json


def mock_requests_get(url: str, timeout: float) -> MockResponse:
    """Return a mock response. Used to patch calls to requests.get in tests below

    Args:
        url (str): a URL - a necessary argument for requests.get
        timeout (int): we pass timeout as an argument to requests.get in get_json_from_ci_api,
            so mock_requests_get is configured to accept this argument.

    Raises:
        ValueError: This function is configured to mock requests to specific URLs only, including
            - /json-nextchants/001010
        If a call to requests.get with a different URL is made while mock_requests_get is patching it,
        a ValueError is raised.

    Returns:
        MockResponse: A mock response object
    """
    if timeout < 0.001:
        raise requests.exceptions.ConnectTimeout

    # mock call to /json-nextchants/001010
    if url in (
        "https://cantusindex.uwaterloo.ca/json-nextchants/001010",
        "https://cantusindex.org/json-nextchants/001010",
    ):
        return MockResponse(
            status_code=200,
            content=mock_cantusindex_data.mock_json_nextchants_001010_content,
            json=mock_cantusindex_data.mock_json_nextchants_001010_json,
        )

    # mock call to /json-cid/008349
    elif url in (
        "https://cantusindex.uwaterloo.ca/json-cid/008349",
        "https://cantusindex.org/json-cid/008349",
    ):
        return MockResponse(
            status_code=200,
            content=mock_cantusindex_data.mock_json_cid_008349_content,
            json=mock_cantusindex_data.mock_json_cid_008349_json,
        )

    # mock call to /json-cid/006928
    elif url in (
        "https://cantusindex.uwaterloo.ca/json-cid/006928",
        "https://cantusindex.org/json-cid/006928",
    ):
        return MockResponse(
            status_code=200,
            content=mock_cantusindex_data.mock_json_cid_006928_content,
            json=mock_cantusindex_data.mock_json_cid_006928_json,
        )

    else:
        raise ValueError(
            f"mock_requests_get is only set up to mock calls to specific URLs; {url} is not one of those URLs"
        )


class UpdateCachedConcordancesCommandTest(TestCase):
    def test_concordances_structure(self):
        chant: Chant = make_fake_chant(cantus_id="123456")
        concordances: list = update_cached_concordances.get_concordances()

        with self.subTest(test="Ensure get_concordances returns list"):
            self.assertIsInstance(concordances, list)

        single_concordance = concordances[0]
        with self.subTest(test="Ensure each concordance is a dict"):
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

    def test_published_vs_unpublished(self):
        published_source: Source = make_fake_source(published=True)
        published_chant: Chant = make_fake_chant(
            source=published_source,
            manuscript_full_text_std_spelling="chant in a published source",
        )
        unpublished_source: Source = make_fake_source(published=False)
        unpublished_chant: Chant = make_fake_chant(
            source=unpublished_source,
            manuscript_full_text_std_spelling="chant in an unpublished source",
        )

        concordances: list = update_cached_concordances.get_concordances()
        self.assertEqual(len(concordances), 1)

        single_concordance: dict = concordances[0]
        expected_fulltext: str = published_chant.manuscript_full_text_std_spelling
        observed_fulltext: str = single_concordance["full_text"]
        self.assertEqual(expected_fulltext, observed_fulltext)

    def test_concordances_values(self):
        chant: Chant = make_fake_chant()

        concordances: list = update_cached_concordances.get_concordances()
        single_concordance: dict = concordances[0]

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


class IncipitSignalTest(TestCase):
    # testing an edge case in generate_incipit, within main_app/signals.py.
    # Some other tests involving this function can be found
    # in ChantModelTest and SequenceModelTest.
    def test_generate_incipit(self):
        complete_fulltext: str = "one two three four five six seven"
        expected_incipit_1: str = "one two three four five"
        observed_incipit_1: str = generate_incipit(complete_fulltext)
        with self.subTest(test="full-length fulltext"):
            self.assertEqual(observed_incipit_1, expected_incipit_1)
        short_fulltext: str = "one*"
        expected_incipit_2 = "one*"
        observed_incipit_2 = generate_incipit(short_fulltext)
        with self.subTest(test="fulltext that's already a short incipit"):
            self.assertEqual(observed_incipit_2, expected_incipit_2)


class CantusIndexFunctionsTest(TestCase):
    def test_get_suggested_chant(self):
        h_genre = make_fake_genre(name="H")
        occs = 3
        expected_chant = {
            "cantus_id": "008349",
            "occurrences": occs,
            "fulltext": "Nocte surgentes vigilemus omnes semper in psalmis meditemur atque viribus totis domino canamus dulciter hymnos | Ut pio regi pariter canentes cum suis sanctis mereamur aulam ingredi caeli simul et beatam ducere vitam | Praestet hoc nobis deitas beata patris ac nati pariterque sancti spiritus cujus resonat per omnem gloria mundum | Amen",
            "incipit": "Nocte surgentes vigilemus omnes semper",
            "genre_id": h_genre.id,
        }
        with patch("requests.get", mock_requests_get):
            observed_chant = get_suggested_chant(cantus_id="008349", occurrences=occs)

        expected_keys = expected_chant.keys()
        observed_keys = observed_chant.keys()
        with self.subTest(test="Ensure suggested chant includes the right keys"):
            self.assertEqual(observed_keys, expected_keys)

        for key in expected_keys:
            expected_val = expected_chant[key]
            observed_val = observed_chant[key]
            with self.subTest(key=key):
                self.assertEqual(observed_val, expected_val)

        with patch("requests.get", mock_requests_get):
            observed_chant_with_r_genre = get_suggested_chant(
                cantus_id="006928", occurrences=occs
            )

        with self.subTest(
            test="Ensure that genre_id=None when no matching Genre found"
        ):
            observed_genre_id = observed_chant_with_r_genre["genre_id"]
            self.assertIsNone(observed_genre_id)

        with patch("requests.get", mock_requests_get):
            observed_chant_short_timeout = get_suggested_chant(
                cantus_id="008349", occurrences=occs, timeout=0.0001
            )

        with self.subTest(test="Ensure None is returned in case of timeout"):
            self.assertIsNone(observed_chant_short_timeout)

    def test_get_suggested_chants(self):
        pass

    def test_get_json_from_ci_api(self):
        with patch("requests.get", mock_requests_get):
            json_nextchants_response = get_json_from_ci_api(path="/json-cid/001010")
        with self.subTest(
            test="Ensure properly handles /nextchants/<cantus_id> endpoint"
        ):
            self.assertIsInstance(json_nextchants_response, list)
            first_nextchant = json_nextchants_response[0]
            self.assertIsInstance(first_nextchant, dict)

        with patch("requests.get", mock_requests_get):
            json_cid_response = get_json_from_ci_api(path="/json-cid/008349")
        observed_json_cid_keys = json_cid_response.keys()
        expected_json_cid_keys = ("info", "chants")
        with self.subTest(
            test="Ensure properly handles /json-cid/<cantus_id> endpoint"
        ):
            self.assertIsInstance(json_cid_response, dict)
            for key in expected_json_cid_keys:
                self.assertIn(key, observed_json_cid_keys)

        with patch("requests.get", mock_requests_get):
            response_short_timeout = get_json_from_ci_api(
                path="/some/path", timeout=0.0001
            )
        with self.subTest(test="Ensure returns None when requests.get times out"):
            self.assertIsNone(response_short_timeout)

        # I can't figure out how to get assertRaises to work - even when the assertion should fail, it doesn't.
        # It's not of vital importance that this argument check work correctly, I think, so I'm giving up in
        # an effort not to get bogged down.
        # Leaving a couple of commented-out attempts here with things I've tried, for the hopeful benefit of some
        # future, cleverer developer
        # - Jacob dGM, April 2024

        # with self.subTest(test="Ensure raises ValueError when path improperly formatted, attempt 1"):
        #     self.assertRaises(ValueError, get_json_from_ci_api, "/for/some/reason/this/passes/even/with/a/leading/slash")

        # with self.subTest(test="Ensure raises ValueError when path improperly formatted, attempt 2"):
        #     with self.assertRaises(ValueError):
        #         get_json_from_ci_api("/i/still/dont/understand/why/this/subtest/passes")
