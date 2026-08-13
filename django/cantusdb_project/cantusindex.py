"""
A collection of functions for fetching data from
Cantus Index's (CI's) various APIs.
"""

import json
import re
from typing import Optional, Union, Callable, TypedDict, Any

import requests
from requests.exceptions import SSLError, Timeout, HTTPError

from main_app.models import Genre

CANTUS_INDEX_DOMAIN: str = "https://cantusindex.uwaterloo.ca"
OLD_CANTUS_INDEX_DOMAIN: str = "https://cantusindex.org"
DEFAULT_TIMEOUT: float = 2  # seconds
NUMBER_OF_SUGGESTED_CHANTS: int = 5  # default number of suggested chants to return
# with the get_suggested_chants function


class SuggestedChant(TypedDict):
    """
    Dictionary containing information required for
    the suggested chants feature on the Chant Create form.
    """

    cantus_id: str
    occurrences: int
    fulltext: Optional[str]
    genre_name: Optional[str]
    genre_id: Optional[int]


def get_suggested_chants(
    cantus_id: str, number_of_suggestions: int = NUMBER_OF_SUGGESTED_CHANTS
) -> Optional[list[SuggestedChant]]:
    """
    Given a Cantus ID, query Cantus Index's /nextchants API for a list of
    Cantus IDs that follow the given Cantus ID in existing manuscripts.
    Sort the list by the number of occurrences of each Cantus ID, and return
    a list of dictionaries containing information about the suggested Cantus IDs
    with the highest number of occurrences.

    Args:
        cantus_id (str): a Cantus ID
        number_of_suggestions (int): the number of suggested Cantus IDs to return

    Returns:
        Optional[list[dict]]: A list of dictionaries, each containing information
        about a suggested Cantus ID:
            - "cantus_id": the suggested Cantus ID
            - "occurrences": the number of times the suggested Cantus ID follows
                the given Cantus ID in existing manuscripts
            - "fulltext": the full text of the suggested Cantus ID
            - "genre_name": the genre of the suggested Cantus ID
            - "genre_id": the ID of the genre of the suggested Cantus ID
            If no suggestions are available, returns None.
    """
    endpoint_path: str = f"/json-nextchants/{cantus_id}"
    all_suggestions = get_json_from_ci_api(endpoint_path)

    if all_suggestions is None:
        return None

    # when Cantus ID doesn't exist within CI, CI's api returns a
    # 200 response with `['Cantus ID is not valid']`
    first_suggestion = all_suggestions[0]
    if not isinstance(first_suggestion, dict):
        return None

    sort_by_occurrences: Callable[[dict[Any, Any]], int] = lambda suggestion: int(
        suggestion["count"]
    )
    sorted_suggestions: list[dict[Any, Any]] = sorted(
        all_suggestions, key=sort_by_occurrences, reverse=True
    )
    trimmed_suggestions = sorted_suggestions[:number_of_suggestions]

    suggested_chants: list[SuggestedChant] = []
    for suggestion in trimmed_suggestions:
        sugg_cantus_id = suggestion["cid"]
        occurences = int(suggestion["count"])
        suggestion_info = suggestion.get("info")
        if suggestion_info:
            fulltext = suggestion_info.get("field_full_text")
            genre_name = suggestion_info.get("field_genre")
        else:
            fulltext = None
            genre_name = None
        try:
            genre_id = Genre.objects.get(name=genre_name).id
        except Genre.DoesNotExist:
            genre_id = None
        suggested_chants.append(
            {
                "cantus_id": sugg_cantus_id,
                "occurrences": occurences,
                "fulltext": fulltext,
                "genre_name": genre_name,
                "genre_id": genre_id,
            }
        )

    return suggested_chants


def get_suggested_fulltext(cantus_id: str) -> Optional[str]:
    endpoint_path: str = f"/json-cid/{cantus_id}"
    json_response: Union[dict, list, None] = get_json_from_ci_api(endpoint_path)

    if not isinstance(json_response, dict):
        # mostly, in case of a timeout within get_json_from_ci_api
        return None

    info: Optional[dict] = json_response.get("info", {}) or {}
    return info.get("field_full_text")


class ClusterElement(TypedDict):
    """One catalogued sub-element of a troped chant, as Cantus Index holds it."""

    cantus_id: str
    genre: Optional[str]
    fulltext: Optional[str]


def get_cantus_id_info(cantus_id: str) -> Optional[dict[Any, Any]]:
    """Return Cantus Index's ``info`` block for a Cantus ID, or None if it has none.

    A Cantus ID that CI doesn't know still answers 200, with ``{"info": null, ...}``
    — so an absent/empty ``info`` is the "no such chant" signal, not an error.
    """
    json_response: Union[dict, list, None] = get_json_from_ci_api(
        f"/json-cid/{cantus_id}"
    )
    if not isinstance(json_response, dict):
        return None
    info = json_response.get("info")
    return info if isinstance(info, dict) and info else None


class BaseChantText(TypedDict):
    """The text to seed a cluster's core from, and the Cantus ID it actually came from."""

    cantus_id: str
    text: Optional[str]


# A Cantus ID is short alphanumerics with optional :/./- separators (g04828, g04828:01,
# 909030). Applied to an ID read out of a *CI response* before that ID is put back into a
# request path — the ids that arrive from the browser are checked by the views. Same
# reasoning either way: nothing but an ID may reshape the request.
CANTUS_ID_PATTERN: re.Pattern = re.compile(r"[A-Za-z0-9.:_-]+")

# CI's longest catalogued ids are well under this. The pattern bounds the character set
# but not the length, so a validated id can still be arbitrarily long; this bound keeps it
# short enough to drop straight into a cache key (memcached rejects keys over 250 bytes).
MAX_CANTUS_ID_LENGTH: int = 64


def get_base_chant_text(cantus_id: str) -> BaseChantText:
    """Return the standard full text to compose ``cantus_id``'s cores from (#2189).

    For a troped chant, the text of the troped record is the base chant and the tropes
    intermingled, *and the base chant's part of it is abbreviated to cue words*: for
    ``g01349.tp14`` Cantus Index holds "... OS JUSTI ... ET LINGUA ... LOQUETUR ...",
    where the base record ``g01349`` holds the whole of "Os justi meditabitur sapientiam
    et lingua ejus loquetur judicium ...". The missing words are in no field of the troped
    record, so no amount of splitting its text recovers them.

    So when CI names a base chant, seed from that instead. The cataloguer then starts from
    complete, clean text and inserts the trope components into it, rather than starting
    from a mess and deleting out of it (Debra Lacoste on #2189, 5 Aug 2026) — and the cores
    they end up with concatenate back to CI's own text for the base chant, which is what
    makes them re-derivable rather than hand-typed.

    CI names it outright, in the troped record's ``field_troped_chant_id``. We follow that
    field and nothing else: deriving the base by stripping a ``.tpNN`` suffix off the ID
    looks tempting and is wrong often enough to matter. Measured over the trope-genre
    chants of a 4,325-text sample of CI:

    - where both are available they agree (58/58 sampled), so the suffix buys no accuracy;
    - the field reaches 43 of 60 sampled tropes whose ID has no strippable suffix at all
      (``ah47439`` → ``509505``), which the suffix cannot reach even in principle;
    - and the two sampled ``.tpNN`` chants with no field resolve, by suffix, to chants
      whose text is unrelated to theirs (``g01280.Tp02`` "Dominus ascendit in thronum
      patris sui" vs ``g01280`` "Sacerdotes dei benedicite dominum") — i.e. the suffix's
      only unique contribution was wrong answers.

    Following the field is one hop, not a walk: the chants it names carry no
    ``field_troped_chant_id`` of their own (10/10 sampled), and it is set on troped records
    only — no ordinary chant in a 70-chant sample carried it, so this changes nothing for
    the untroped chants that are the bulk of cataloguing.

    Returns the base chant's ID and text when there is one to seed from, and otherwise the
    requested chant's own ID and text — which is the pre-#2189 behaviour, and what the
    automatic split still exists for. ``text`` is None when CI has no text for either,
    a normal outcome the composer handles by letting the cataloguer type the text in.
    """
    info: dict[Any, Any] = get_cantus_id_info(cantus_id) or {}
    base_id: str = str(info.get("field_troped_chant_id") or "").strip()
    if base_id and base_id != cantus_id and CANTUS_ID_PATTERN.fullmatch(base_id):
        base_info: dict[Any, Any] = get_cantus_id_info(base_id) or {}
        base_text: str = str(base_info.get("field_full_text") or "").strip()
        # An empty base record is no use to seed from; fall through to the chant's own text
        # rather than handing back a blank composer.
        if base_text:
            return {"cantus_id": base_id, "text": base_text}

    own_text: str = str(info.get("field_full_text") or "").strip()
    return {"cantus_id": cantus_id, "text": own_text or None}


def get_cluster_elements(
    cantus_id: str,
    max_elements: int = 40,
    max_consecutive_misses: int = 2,
) -> Optional[list[ClusterElement]]:
    """Collect the catalogued sub-elements of a troped chant, e.g. g04828:01…:04.

    Cantus Index has no endpoint that lists a chant's constituent elements, and none
    that lists Cantus IDs in bulk (``/json-cantusids``, which the CantusDB wiki cites,
    404s on both CI hosts as of 2026-08). What CI *does* expose is each sub-element as
    a chant in its own right — ``/json-cid/g04828:01`` is a full record — so the only
    way to enumerate them is to walk the numbering until it runs out.

    Sub-elements are numbered from 01 in a contiguous, zero-padded run, so we probe in
    order and stop after ``max_consecutive_misses`` gaps (tolerating a single hole in
    the sequence) or ``max_elements`` probes, whichever comes first. Callers should
    cache the result: this costs one upstream request per probe.

    Returns the elements in order, an empty list when Cantus Index is reachable but the
    chant has no catalogued elements, or ``None`` when CI couldn't be reached to find
    out. Empty and unreachable have to be told apart because a caller caches the answer:
    caching an empty list is right, caching an outage hides a troped chant's whole bank
    for as long as the cache lives. ``get_cantus_id_info`` collapses both to None (a
    timeout and a genuine "no such element" both return it), so we read the transport
    layer directly here — a None from ``get_json_from_ci_api`` is a failed request, not
    an absent element — and abandon the walk rather than report a short or empty run CI
    never actually confirmed.

    Known limitation: only the ``<parent>:NN`` form is discoverable this way. A
    sub-element using another suffix convention (``<parent>.Tp7``) can't be guessed at
    and won't appear — it stays reachable through the text search instead.
    """
    elements: list[ClusterElement] = []
    consecutive_misses: int = 0
    for number in range(1, max_elements + 1):
        sub_id: str = f"{cantus_id}:{number:02d}"
        response: Union[dict[Any, Any], list[Any], None] = get_json_from_ci_api(
            f"/json-cid/{sub_id}"
        )
        if response is None:
            return None
        info = response.get("info") if isinstance(response, dict) else None
        if not (isinstance(info, dict) and info):
            consecutive_misses += 1
            if consecutive_misses >= max_consecutive_misses:
                break
            continue
        consecutive_misses = 0
        fulltext: Optional[str] = info.get("field_full_text")
        elements.append(
            {
                "cantus_id": sub_id,
                "genre": info.get("field_genre"),
                "fulltext": fulltext.strip() if fulltext else None,
            }
        )
    return elements


def get_merged_cantus_ids() -> Optional[list[Optional[dict]]]:
    """Retrieve merged Cantus IDs from the Cantus Index API (/json-merged-chants)

    This function sends a request to the Cantus Index API endpoint for merged chants
    and retrieves the response. The response is expected to be a list of dictionaries,
    each containing information about a merged Cantus ID, including the old Cantus ID,
    the new Cantus ID, and the date of the merge.

    Returns:
        Optional[list]: A list of dictionaries representing merged chant information,
    or None if there was an error retrieving the data or the response format is invalid.

    """
    endpoint_path: str = "/json-merged-chants"

    # We have to use the old CI domain since the API is still not available on
    # cantusindex.uwaterloo.ca. Once it's available, we can use get_json_from_ci_api
    # json: Union[dict, list, None] = get_json_from_ci_api(endpoint_path)
    uri: str = f"{OLD_CANTUS_INDEX_DOMAIN}{endpoint_path}"
    try:
        response: requests.Response = requests.get(uri, timeout=DEFAULT_TIMEOUT)
    except (SSLError, Timeout, HTTPError):
        return None
    if not response.status_code == 200:
        return None
    response.encoding = "utf-8-sig"
    raw_text: str = response.text
    text_without_bom: str = raw_text.encode().decode("utf-8-sig")
    if not text_without_bom:
        return None
    merge_events: list = json.loads(text_without_bom)

    if not isinstance(merge_events, list):
        return None
    return merge_events


def get_ci_text_search(search_term: str) -> Optional[list[Optional[dict]]]:
    """Fetch data from Cantus Index for a given search term.
    To do a text search on CI, we use 'https://cantusindex.org/json-text/<text to search>
    """

    # We have to use the old CI domain since this API is still not available on
    # cantusindex.uwaterloo.ca. Once it's available, we can use get_json_from_ci_api
    # json: Union[dict, list, None] = get_json_from_ci_api(uri)
    endpoint_path: str = f"/json-text/{search_term}"
    uri: str = f"{OLD_CANTUS_INDEX_DOMAIN}{endpoint_path}"
    try:
        response: requests.Response = requests.get(
            uri,
            timeout=DEFAULT_TIMEOUT,
        )
    except (SSLError, Timeout, HTTPError):
        return None
    if not response.status_code == 200:
        return None
    response.encoding = "utf-8-sig"
    raw_text: str = response.text
    text_without_bom: str = raw_text.encode().decode("utf-8-sig")
    if not text_without_bom:
        return None
    text_search_results: list = json.loads(text_without_bom)
    # Return None for any non-list response (malformed JSON, unexpected type, etc.); an empty list means CI found no matches
    if not isinstance(text_search_results, list):
        return None

    return text_search_results


def get_json_from_ci_api(
    path: str, timeout: float = DEFAULT_TIMEOUT
) -> Union[dict[Any, Any], list[Any], None]:
    """Given a path, send a request to Cantus Index at that path,
    decode the response to remove its Byte Order Marker, parse it,
    and return it as a dictionary or list.

    Args:
        path (str): The path of the Cantus Index endpoint, including a leading "/"
        timeout (int): how long to wait for a response before giving
            up and returning None.

    Returns:
        Union[dict, list, None]:
            If the JSON returned from Cantus Index is a JSON object, returns a dict.
            If the JSON returned is a JSON array, returns a list.
            If the request times out, or other types are returned, returns None.
    """

    if not path.startswith("/"):
        raise ValueError('path must begin with "/"')

    uri = f"{CANTUS_INDEX_DOMAIN}{path}"
    try:
        response: requests.Response = requests.get(uri, timeout=timeout)
    except requests.exceptions.RequestException:
        return None

    if not response.status_code == 200:
        return None  # /json-cid/Non-existentCantusId returns a 500 page

    response.encoding = "utf-8-sig"

    if not response.text.strip():
        # /json-nextchants returns a response with text='\r\n' in situations where
        # there are no suggested chants
        return None

    try:
        parsed_response = response.json()
    except ValueError:
        return None

    if not isinstance(parsed_response, (dict, list)):
        return None

    return parsed_response
