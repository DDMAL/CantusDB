"""
A collection of functions for fetching data from
Cantus Index's (CI's) various APIs.
"""

import json
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


def get_cluster_elements(
    cantus_id: str,
    max_elements: int = 40,
    max_consecutive_misses: int = 2,
) -> list[ClusterElement]:
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

    Known limitation: only the ``<parent>:NN`` form is discoverable this way. A
    sub-element using another suffix convention (``<parent>.Tp7``) can't be guessed at
    and won't appear — it stays reachable through the text search instead.
    """
    elements: list[ClusterElement] = []
    consecutive_misses: int = 0
    for number in range(1, max_elements + 1):
        sub_id: str = f"{cantus_id}:{number:02d}"
        info: Optional[dict[Any, Any]] = get_cantus_id_info(sub_id)
        if not info:
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
