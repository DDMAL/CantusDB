from typing import Union, Optional
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
import requests
from requests.exceptions import SSLError, Timeout, HTTPError
from main_app.models.url_field import NormalizedURLField, NormalizedURLFormField
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
    get_base_chant_text,
    get_cluster_elements,
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
        if url.endswith("no_match"):
            return MockResponse(
                status_code=200,
                content=mock_cantusindex_data.mock_get_ci_text_search_no_match_content,
                text=mock_cantusindex_data.mock_get_ci_text_search_no_match_text,
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

        def raise_connection_error(*args, **kwargs):
            raise requests.exceptions.ConnectionError

        with patch("requests.get", raise_connection_error):
            response_connection_error = get_json_from_ci_api(path="/json-cids")
        with self.subTest(
            test="Ensure returns None when requests.get raises a connection error"
        ):
            self.assertIsNone(response_connection_error)

        malformed_json_response = MockResponse(
            status_code=200,
            text="this is not valid json",
            json=None,
            content=b"this is not valid json",
        )

        def json_raises_value_error():
            raise ValueError("Expecting value")

        malformed_json_response.json = json_raises_value_error
        with patch("requests.get", lambda *args, **kwargs: malformed_json_response):
            response_malformed_json = get_json_from_ci_api(path="/json-cids")
        with self.subTest(
            test="Ensure returns None when Cantus Index returns malformed JSON"
        ):
            self.assertIsNone(response_malformed_json)

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


class GetBaseChantTextTest(TestCase):
    """
    Resolving the text to seed a cluster's cores from (#2189).

    A troped chant's own text has the base chant abbreviated to cue words, so the composer
    seeds from the base chant instead — and Cantus Index names that chant itself, in
    ``field_troped_chant_id``. These tests pin that the field is what's followed, exactly
    one hop, with the chant's own text as the fallback.
    """

    @staticmethod
    def _fake_ci(known: dict) -> "callable":
        """A get_json_from_ci_api stand-in serving only the Cantus IDs in ``known``."""

        def fake(path: str, *args, **kwargs) -> dict:
            cantus_id = path.rsplit("/", 1)[-1]
            if cantus_id in known:
                return {"info": known[cantus_id]}
            return {"info": None, "databases": [], "chants": []}

        return fake

    # The real records, trimmed: g01349.tp14's text holds the base chant as the cues
    # OS JUSTI / ET LINGUA, where g01349 holds the words those cues stand for.
    TROPED_CHANT = {
        "field_genre": "TpIn",
        "field_full_text": (
            "Hac in laude patris cuncti dicamus ovanter OS JUSTI "
            "Qui nosmet hodie facit esse de se jucundos ET LINGUA"
        ),
        "field_troped_chant_id": "g01349",
    }
    BASE_CHANT = {
        "field_genre": "In",
        "field_full_text": (
            "Os justi meditabitur sapientiam et lingua ejus loquetur judicium"
        ),
        "field_troped_chant_id": None,
    }

    def test_seeds_from_the_base_chant_cantus_index_names(self) -> None:
        known = {"g01349.tp14": self.TROPED_CHANT, "g01349": self.BASE_CHANT}
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci(known)):
            resolved = get_base_chant_text("g01349.tp14")
        self.assertEqual(resolved["cantus_id"], "g01349")
        self.assertEqual(resolved["text"], self.BASE_CHANT["field_full_text"])

    def test_untroped_chant_keeps_its_own_text(self) -> None:
        """The overwhelming majority of chants; nothing about them changed in #2189."""
        known = {"008349": {"field_full_text": "Nocte surgentes vigilemus omnes"}}
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci(known)):
            resolved = get_base_chant_text("008349")
        self.assertEqual(
            resolved, {"cantus_id": "008349", "text": "Nocte surgentes vigilemus omnes"}
        )

    def test_falls_back_to_own_text_when_the_named_base_has_none(self) -> None:
        """CI names a base chant it holds no text for. Seeding from the troped chant's own
        text is the pre-#2189 behaviour, and the automatic split still applies to it — an
        empty composer would be strictly worse."""
        known = {
            "g01349.tp14": self.TROPED_CHANT,
            "g01349": {"field_full_text": "  ", "field_troped_chant_id": None},
        }
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci(known)):
            resolved = get_base_chant_text("g01349.tp14")
        self.assertEqual(resolved["cantus_id"], "g01349.tp14")
        self.assertEqual(resolved["text"], self.TROPED_CHANT["field_full_text"])

    def test_falls_back_when_the_named_base_is_not_in_cantus_index(self) -> None:
        with patch(
            "cantusindex.get_json_from_ci_api",
            self._fake_ci({"g01349.tp14": self.TROPED_CHANT}),
        ):
            resolved = get_base_chant_text("g01349.tp14")
        self.assertEqual(resolved["cantus_id"], "g01349.tp14")
        self.assertEqual(resolved["text"], self.TROPED_CHANT["field_full_text"])

    def test_does_not_follow_a_suffix_cantus_index_has_not_confirmed(self) -> None:
        """The tempting shortcut — strip `.tpNN` and fetch that — is not what happens.
        Measured over CI, a `.tpNN` chant with no `field_troped_chant_id` resolves by
        suffix to a chant whose text is unrelated to its own (g01280.Tp02 vs g01280), so
        the suffix is not evidence of anything and the chant keeps its own text."""
        known = {
            "g01280.Tp02": {
                "field_full_text": "Dominus ascendit in thronum patris sui alleluia eia",
                "field_troped_chant_id": None,
            },
            "g01280": {
                "field_full_text": "Sacerdotes dei benedicite dominum sancti et humiles",
                "field_troped_chant_id": None,
            },
        }
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci(known)):
            resolved = get_base_chant_text("g01280.Tp02")
        self.assertEqual(resolved["cantus_id"], "g01280.Tp02")
        self.assertEqual(resolved["text"], known["g01280.Tp02"]["field_full_text"])

    def test_follows_the_field_exactly_one_hop(self) -> None:
        """No CI chant was found pointing at a chant that points on again, but a chain must
        not turn into a walk (nor, if CI ever holds a cycle, into a loop)."""
        known = {
            "a": {"field_full_text": "text a", "field_troped_chant_id": "b"},
            "b": {"field_full_text": "text b", "field_troped_chant_id": "c"},
            "c": {"field_full_text": "text c", "field_troped_chant_id": None},
        }
        calls: list = []

        def counting(path: str, *args, **kwargs) -> dict:
            calls.append(path)
            return self._fake_ci(known)(path)

        with patch("cantusindex.get_json_from_ci_api", counting):
            resolved = get_base_chant_text("a")
        self.assertEqual(resolved, {"cantus_id": "b", "text": "text b"})
        self.assertEqual(calls, ["/json-cid/a", "/json-cid/b"])

    def test_self_reference_does_not_double_fetch(self) -> None:
        known = {
            "g01349": {"field_full_text": "Os justi", "field_troped_chant_id": "g01349"}
        }
        calls: list = []

        def counting(path: str, *args, **kwargs) -> dict:
            calls.append(path)
            return self._fake_ci(known)(path)

        with patch("cantusindex.get_json_from_ci_api", counting):
            resolved = get_base_chant_text("g01349")
        self.assertEqual(resolved, {"cantus_id": "g01349", "text": "Os justi"})
        self.assertEqual(len(calls), 1)

    def test_unknown_chant_has_no_text(self) -> None:
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci({})):
            self.assertEqual(
                get_base_chant_text("999999"), {"cantus_id": "999999", "text": None}
            )

    def test_a_base_id_that_is_not_a_cantus_id_is_not_requested(self) -> None:
        """The base ID arrives in a CI *response* and is then put into a CI *request* path,
        which the views' own guard on incoming IDs does not cover. Nothing that isn't
        shaped like a Cantus ID gets that far."""
        known = {
            "g01349.tp14": {
                "field_full_text": "Hac in laude patris OS JUSTI",
                "field_troped_chant_id": "../json-text/anything?x=1",
            }
        }
        calls: list = []

        def counting(path: str, *args, **kwargs) -> dict:
            calls.append(path)
            return self._fake_ci(known)(path)

        with patch("cantusindex.get_json_from_ci_api", counting):
            resolved = get_base_chant_text("g01349.tp14")
        self.assertEqual(calls, ["/json-cid/g01349.tp14"])
        self.assertEqual(resolved["cantus_id"], "g01349.tp14")

    def test_strips_whitespace_cantus_index_leaves_on_the_text(self) -> None:
        """field_full_text carries trailing whitespace, and this text becomes a core
        element's own text — the same reason get_cluster_elements strips it."""
        known = {"008349": {"field_full_text": "  Nocte surgentes vigilemus  "}}
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci(known)):
            self.assertEqual(
                get_base_chant_text("008349")["text"], "Nocte surgentes vigilemus"
            )


class GetClusterElementsTest(TestCase):
    """
    Walking a troped chant's sub-elements (#2129).

    Cantus Index exposes no endpoint listing a chant's elements, so they're found by
    probing ``/json-cid/<parent>:NN`` in order. A Cantus ID CI doesn't hold still
    answers 200, with ``{"info": null, ...}`` — that null is the "no such element"
    signal these tests stand in for.
    """

    @staticmethod
    def _fake_ci(known: dict) -> "callable":
        """A get_json_from_ci_api stand-in serving only the Cantus IDs in ``known``."""

        def fake(path: str, *args, **kwargs) -> dict:
            cantus_id = path.rsplit("/", 1)[-1]
            if cantus_id in known:
                return {"info": known[cantus_id]}
            return {"info": None, "databases": [], "chants": []}

        return fake

    def test_collects_contiguous_elements_then_stops(self) -> None:
        known = {
            f"g04828:{i:02d}": {
                "field_genre": "TpSa",
                "field_full_text": f"element {i}",
            }
            for i in range(1, 4)
        }
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci(known)):
            elements = get_cluster_elements("g04828")
        self.assertEqual(
            [element["cantus_id"] for element in elements],
            ["g04828:01", "g04828:02", "g04828:03"],
        )
        self.assertEqual(elements[0]["genre"], "TpSa")

    def test_strips_whitespace_from_fulltext(self) -> None:
        """CI's field_full_text carries trailing whitespace; it becomes a token's text."""
        known = {
            "g04828:01": {
                "field_genre": "TpSa",
                "field_full_text": "Perpetuo numine cuncta regens ",
            }
        }
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci(known)):
            elements = get_cluster_elements("g04828")
        self.assertEqual(elements[0]["fulltext"], "Perpetuo numine cuncta regens")

    def test_skips_a_catalogued_element_with_no_text(self) -> None:
        """A sub-element CI holds without text can't be composed and would show as a
        blank chip, so it's dropped — but it still counts toward the walk, so a later
        numbered element is not treated as the end of the run."""
        known = {
            "g04828:01": {"field_genre": "TpSa", "field_full_text": "first"},
            "g04828:02": {"field_genre": "TpSa", "field_full_text": "   "},
            "g04828:03": {"field_genre": "TpSa", "field_full_text": "third"},
        }
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci(known)):
            elements = get_cluster_elements("g04828")
        self.assertEqual(
            [element["cantus_id"] for element in elements], ["g04828:01", "g04828:03"]
        )

    def test_tolerates_a_single_gap_in_the_numbering(self) -> None:
        """One missing number is a hole in CI's catalogue, not the end of the run."""
        known = {
            "g04828:01": {"field_genre": "TpSa", "field_full_text": "first"},
            "g04828:03": {"field_genre": "TpSa", "field_full_text": "third"},
        }
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci(known)):
            elements = get_cluster_elements("g04828")
        self.assertEqual(
            [element["cantus_id"] for element in elements], ["g04828:01", "g04828:03"]
        )

    def test_untroped_chant_yields_no_elements(self) -> None:
        """CI reachable, chant has none: an empty list, which the caller may cache."""
        with patch("cantusindex.get_json_from_ci_api", self._fake_ci({})):
            self.assertEqual(get_cluster_elements("008349"), [])

    def test_unreachable_ci_yields_none_not_an_empty_list(self) -> None:
        """A transport failure is not a "no such element" 200. get_json_from_ci_api
        returns None for both, so the walk reads it directly and reports None — distinct
        from [], so the caller caches a real empty answer but not an outage."""
        with patch("cantusindex.get_json_from_ci_api", return_value=None):
            self.assertIsNone(get_cluster_elements("g04828"))

    def test_a_failure_partway_abandons_the_run(self) -> None:
        """A blip after some elements are found still leaves the count unknown, so the
        partial run is discarded rather than reported as the whole of it."""
        known = {
            "g04828:01": {"field_genre": "TpSa", "field_full_text": "first"},
            "g04828:02": {"field_genre": "TpSa", "field_full_text": "second"},
        }

        def flaky(path: str, *args, **kwargs):
            cantus_id = path.rsplit("/", 1)[-1]
            if cantus_id in known:
                return {"info": known[cantus_id]}
            return None  # CI drops on the first probe past the known elements

        with patch("cantusindex.get_json_from_ci_api", flaky):
            self.assertIsNone(get_cluster_elements("g04828"))

    def test_stops_probing_at_max_elements(self) -> None:
        """An unbroken run can't drive an unbounded number of upstream requests."""
        known = {
            f"g04828:{i:02d}": {
                "field_genre": "TpSa",
                "field_full_text": f"element {i}",
            }
            for i in range(1, 40)
        }
        calls: list = []

        def counting(path: str, *args, **kwargs) -> dict:
            calls.append(path)
            return self._fake_ci(known)(path)

        with patch("cantusindex.get_json_from_ci_api", counting):
            elements = get_cluster_elements("g04828", max_elements=5)
        self.assertEqual(len(elements), 5)
        self.assertEqual(len(calls), 5)


class NormalizedURLFormFieldTest(TestCase):
    def setUp(self):
        self.field = NormalizedURLFormField(required=False)

    def test_spaces_encoded(self):
        result = self.field.clean("https://example.com/Folio 92r.jpg")
        self.assertEqual(
            result,
            "https://example.com/Folio%2092r.jpg",
        )

    def test_already_encoded_unchanged(self):
        url = "https://example.com/Folio%2092r.jpg"
        self.assertEqual(self.field.clean(url), url)

    def test_leading_trailing_whitespace_stripped(self):
        result = self.field.clean("  https://example.com/image.jpg  ")
        self.assertEqual(result, "https://example.com/image.jpg")

    def test_spaces_in_query_string_encoded(self):
        result = self.field.clean("https://example.com/search?q=some query")
        self.assertEqual(result, "https://example.com/search?q=some%20query")

    def test_invalid_url_rejected(self):
        with self.assertRaises(ValidationError):
            self.field.clean("not a url at all")

    def test_empty_string_returns_empty(self):
        self.assertEqual(self.field.clean(""), "")


class NormalizedURLModelFieldTest(TestCase):
    """Covers code paths that skip forms (admin, management commands, ORM)."""

    def setUp(self):
        self.field = NormalizedURLField(blank=True, null=True)

    def test_to_python_encodes_spaces(self):
        self.assertEqual(
            self.field.to_python("https://example.com/Folio 92r.jpg"),
            "https://example.com/Folio%2092r.jpg",
        )

    def test_get_prep_value_encodes_spaces(self):
        # Exercised on direct .save() even without full_clean().
        self.assertEqual(
            self.field.get_prep_value("https://example.com/Folio 92r.jpg"),
            "https://example.com/Folio%2092r.jpg",
        )

    def test_deconstruct_reports_as_plain_urlfield(self):
        # Keeps makemigrations from generating a no-op migration.
        _, path, _, _ = self.field.deconstruct()
        self.assertEqual(path, "django.db.models.URLField")

    def test_formfield_returns_normalizing_form_field(self):
        self.assertIsInstance(self.field.formfield(), NormalizedURLFormField)


class ImageLinkSpaceEncodingIntegrationTest(TestCase):
    """End-to-end coverage: saving a model whose image_link
    contains spaces must succeed and persist the URL with spaces encoded."""

    def test_chant_with_spaced_image_link_saves(self) -> None:
        # Mirrors the management-command path from #1868: a direct .save(),
        # which BaseModel.save() routes through full_clean()/URLValidator.
        chant = make_fake_chant()
        chant.image_link = "https://example.com/Folio 92r.jpg"
        chant.save()
        chant.refresh_from_db()
        self.assertEqual(chant.image_link, "https://example.com/Folio%2092r.jpg")

    def test_source_with_spaced_image_link_saves(self) -> None:
        source = make_fake_source()
        source.image_link = "https://example.com/image gallery.jpg"
        source.save()
        source.refresh_from_db()
        self.assertEqual(source.image_link, "https://example.com/image%20gallery.jpg")

    def test_save_does_not_raise_on_spaces(self) -> None:
        # Without the fix this raises ValidationError ("Enter a valid URL"),
        # which is exactly the failure reported in #1868.
        chant = make_fake_chant()
        chant.image_link = "https://example.com/a b c.jpg"
        try:
            chant.save()
        except ValidationError:
            self.fail("Saving a chant with spaces in image_link should not raise.")
