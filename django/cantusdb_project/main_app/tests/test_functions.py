from typing import Union, Optional
from unittest.mock import patch


from django.test import TestCase
import requests
from requests.exceptions import SSLError, Timeout, HTTPError
from main_app.models import (
    Chant,
    Source,
)
from main_app.tests import mock_cantusindex_data
from main_app.tests.make_fakes import (
    make_fake_chant,
    make_fake_source,
)
from main_app.management.commands import update_cached_concordances
from main_app.signals import generate_incipit
from cantusindex import (
    get_suggested_chants,
    get_json_from_ci_api,
    CANTUS_INDEX_DOMAIN,
    OLD_CANTUS_INDEX_DOMAIN,
    get_suggested_fulltext,
    get_merged_cantus_ids,
    get_ci_text_search,
)

# run with `python -Wa manage.py test main_app.tests.test_functions`
# the -Wa flag tells Python to display deprecation warnings


class MockResponse:
    def __init__(
        self,
        status_code: int,
        text: Optional[str],
        json: Union[dict, list, None],
        content: Optional[bytes],
        encoding: str = "utf-8",
        # >>> response = requests.get("https://cantusindex.uwaterloo.ca/json-nextchants/001010")
        # >>> response.encoding
        # 'utf-8'
    ):
        self.status_code = status_code
        self._json = json
        self.content = content
        self.encoding = encoding
        self.text = text

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
        If a call to requests.get with a different URL is made while mock_requests_get
        is patching it, a NotImplementedError is raised.

    Returns:
        MockResponse: A mock response object
    """
    if timeout < 0.001:
        raise requests.exceptions.ConnectTimeout

    if not (CANTUS_INDEX_DOMAIN or OLD_CANTUS_INDEX_DOMAIN in url):
        raise NotImplementedError(
            f"mock_requests_get is only set up to mock calls to Cantus Index. "
            f"The protocol and domain of url {url} do not correspond to those of Cantus Index."
        )

    if f"{CANTUS_INDEX_DOMAIN}/json-nextchants/" in url:
        if url.endswith("/001010"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_nextchants_001010_content,
                text=mock_cantusindex_data.mock_json_nextchants_001010_text,
                json=mock_cantusindex_data.mock_json_nextchants_001010_json,
            )
        if url.endswith("/a07763"):
            # this Cantus ID has no suggested chants
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_nextchants_a07763_content,
                text=mock_cantusindex_data.mock_json_nextchants_a07763_text,
                json=None,
            )
        # imitating CI's behavior when a made-up Cantus ID is entered.
        return MockResponse(
            status_code=200,
            content=bytes('["Cantus ID is not valid"]', encoding="utf-8-sig"),
            text='["Cantus ID is not valid"]',
            json=["Cantus ID is not valid"],
        )
    if f"{CANTUS_INDEX_DOMAIN}/json-cid/" in url:
        if url.endswith("/008349"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_008349_content,
                text=mock_cantusindex_data.mock_json_cid_008349_text,
                json=mock_cantusindex_data.mock_json_cid_008349_json,
            )
        if url.endswith("/006928"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_006928_content,
                text=mock_cantusindex_data.mock_json_cid_006928_text,
                json=mock_cantusindex_data.mock_json_cid_006928_json,
            )
        if url.endswith("/008411c"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_008411c_content,
                text=mock_cantusindex_data.mock_json_cid_008411c_text,
                json=mock_cantusindex_data.mock_json_cid_008411c_json,
            )
        if url.endswith("/008390"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_008390_content,
                text=mock_cantusindex_data.mock_json_cid_008390_text,
                json=mock_cantusindex_data.mock_json_cid_008390_json,
            )
        if url.endswith("/007713"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_007713_content,
                text=mock_cantusindex_data.mock_json_cid_007713_text,
                json=mock_cantusindex_data.mock_json_cid_007713_json,
            )
        if url.endswith("/909030"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_json_cid_909030_content,
                text=mock_cantusindex_data.mock_json_cid_909030_text,
                json=mock_cantusindex_data.mock_json_cid_909030_json,
            )
        # imitating CI's behavior when a made-up Cantus ID is entered.
        return MockResponse(
            status_code=500,
            content=None,
            text=None,
            json=None,
        )
    if f"{OLD_CANTUS_INDEX_DOMAIN}/json-text/" in url:
        if url.endswith("qui+est"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_get_ci_text_search_quiest_content,
                text=mock_cantusindex_data.mock_get_ci_text_search_quiest_text,
                json=None,
            )
        if url.endswith("123xyz"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_get_ci_text_search_123xyz_content,
                text=mock_cantusindex_data.mock_get_ci_text_search_123xyz_text,
                json=None,
            )
        return MockResponse(
            status_code=500,
            content=None,
            text=None,
            json=None,
        )
    if f"{OLD_CANTUS_INDEX_DOMAIN}/json-merged-chants" in url:
        return MockResponse(
            status_code=200,
            content=mock_cantusindex_data.mock_get_merged_cantus_ids_content,
            text=mock_cantusindex_data.mock_get_merged_cantus_ids_text,
            json=None,
        )

    raise NotImplementedError(
        f"mock_requests_get is only set up to imitate only the /json-nextchants/, "
        f"/json-cid/, and /json-text/ endpoints on Cantus Index. The path of the url "
        f"{url} does not match either of these endpoints."
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
            ("office", chant.service.name),
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
    def test_get_suggested_chants(self) -> None:
        expected_number_of_suggestions: int = 5
        with patch("requests.get", mock_requests_get):
            suggested_chants = get_suggested_chants(cantus_id="001010")

        initial_suggested_chant = suggested_chants[0]

        with self.subTest(test="Ensure returned object is a list of dicts"):
            self.assertIsInstance(suggested_chants, list)
            self.assertIsInstance(initial_suggested_chant, dict)

        with self.subTest(
            test=f"Ensure no more than {expected_number_of_suggestions} suggestions returned"
        ):
            self.assertLessEqual(len(suggested_chants), expected_number_of_suggestions)

        with self.subTest(
            test="Ensure suggested chants are ordered by number of occurrences"
        ):
            for i in range(expected_number_of_suggestions - 1):
                suggested_chant = suggested_chants[i]
                following_suggested_chant = suggested_chants[i + 1]
                self.assertGreaterEqual(
                    suggested_chant["occurrences"],
                    following_suggested_chant["occurrences"],
                )

        with patch("requests.get", mock_requests_get):
            suggested_chants_nonexistent_cantus_id = get_suggested_chants(
                "NotACantusID"
            )
        with self.subTest(test="Ensure None returned in case of nonexistent Cantus ID"):
            self.assertIsNone(suggested_chants_nonexistent_cantus_id)

        with patch("requests.get", mock_requests_get):
            suggested_chants_rare_cantus_id = get_suggested_chants(cantus_id="a07763")
        with self.subTest(
            test="Ensure None is returned in case of Cantus ID without suggestions"
        ):
            self.assertIsNone(suggested_chants_rare_cantus_id)

    def test_get_json_from_ci_api(self) -> None:
        with patch("requests.get", mock_requests_get):
            json_nextchants_response = get_json_from_ci_api(
                path="/json-nextchants/001010"
            )
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

        with patch("requests.get", mock_requests_get):
            response_nonexistent_cantus_id = get_json_from_ci_api(
                path="/json-cid/notACantusID"
            )
        with self.subTest(
            test="Ensure returns None when response status code is not 200"
        ):
            self.assertIsNone(response_nonexistent_cantus_id)

        with self.subTest(
            test="Ensure raises ValueError when path lacks leading slash"
        ):
            self.assertRaises(
                ValueError, get_json_from_ci_api, "path/lacking/a/leading/slash"
            )

    def test_get_suggested_fulltext(self) -> None:
        with self.subTest("Test CantusID with full text"):
            with patch("requests.get", mock_requests_get):
                fulltext = get_suggested_fulltext("008349")
            self.assertEqual(
                fulltext,
                "Nocte surgentes vigilemus omnes semper in psalmis meditemur atque viribus totis domino canamus dulciter hymnos | Ut pio regi pariter canentes cum suis sanctis mereamur aulam ingredi caeli simul et beatam ducere vitam | Praestet hoc nobis deitas beata patris ac nati pariterque sancti spiritus cujus resonat per omnem gloria mundum | Amen",
            )

        with self.subTest("Test invalid CantusID"):
            with patch("requests.get", mock_requests_get):
                fulltext = get_suggested_fulltext("999999")
            self.assertIsNone(fulltext)

    def test_get_merged_cantus_ids(self) -> None:
        with self.subTest("Test valid response"):
            with patch("requests.get", mock_requests_get):
                results = get_merged_cantus_ids()
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 20)
            self.assertEqual(results[0]["old"], "g00831")
            self.assertEqual(results[0]["new"], "920023")
            self.assertEqual(results[0]["date"], "0000-00-00")

        with self.subTest("Test server error"):
            mock_response = MockResponse(
                status_code=500,
                text=None,
                json=None,
                content=None,
            )
            with patch("requests.get", return_value=mock_response):
                results = get_merged_cantus_ids()
            self.assertIsNone(results)

        with self.subTest("Test timeout"):
            with patch("requests.get", side_effect=Timeout):
                results = get_merged_cantus_ids()
            self.assertRaises(Timeout)
            self.assertIsNone(results)

        with self.subTest("Test SSLError"):
            with patch("requests.get", side_effect=SSLError):
                results = get_merged_cantus_ids()
            self.assertRaises(SSLError)
            self.assertIsNone(results)

        with self.subTest("Test HTTPError"):
            with patch("requests.get", side_effect=HTTPError):
                results = get_merged_cantus_ids()
            self.assertRaises(HTTPError)
            self.assertIsNone(results)

    def test_get_ci_text_search(self) -> None:
        with self.subTest("Test valid search term"):
            with patch("requests.get", mock_requests_get):
                results = get_ci_text_search("qui+est")
            self.assertIsInstance(results, list)
            self.assertEqual(len(results), 50)
            self.assertEqual(results[0]["cid"], "001774")
            self.assertEqual(
                results[0]["fulltext"],
                "Caro et sanguis non revelavit tibi sed pater meus qui est in caelis",
            )
            self.assertEqual(results[1]["cid"], "002191")
            self.assertEqual(
                results[1]["fulltext"],
                "Dicebat Jesus turbis Judaeorum et principibus sacerdotum qui est ex deo verba dei audit responderunt Judaei et dixerunt ei nonne bene dicimus nos quia Samaritanus es tu et daemonium habes respondit Jesus ego daemonium non habeo sed honorifico patrem meum et vos inhonorastis me",
            )

        with self.subTest("Test invalid search term"):
            with patch("requests.get", mock_requests_get):
                results = get_ci_text_search("123xyz")
            self.assertIsNone(results)

        with self.subTest("Test server error"):
            mock_response = MockResponse(
                status_code=500,
                text=None,
                json=None,
                content=None,
            )
            with patch("requests.get", return_value=mock_response):
                results = get_ci_text_search("server_error")
            self.assertIsNone(results)

        with self.subTest("Test SSLError"):
            with patch("requests.get", side_effect=SSLError):
                results = get_ci_text_search("SSLError")
            self.assertRaises(SSLError)
            self.assertIsNone(results)

        with self.subTest("Test Timeout"):
            with patch("requests.get", side_effect=Timeout):
                results = get_ci_text_search("Timeout")
            self.assertRaises(Timeout)
            self.assertIsNone(results)

        with self.subTest("Test HTTPError"):
            with patch("requests.get", side_effect=HTTPError):
                results = get_ci_text_search("HTTPError")
            self.assertRaises(HTTPError)
            self.assertIsNone(results)
