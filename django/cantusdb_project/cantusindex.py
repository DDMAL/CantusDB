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

    try:
        suggested_fulltext = json_response["info"]["field_full_text"]
    except KeyError:
        return None

    return suggested_fulltext


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
    # if cantus index returns an empty table
    if not text_search_results or not isinstance(text_search_results, list):
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
    except requests.exceptions.Timeout:
        return None

    if not response.status_code == 200:
        return None  # /json-cid/Non-existentCantusId returns a 500 page

    response.encoding = "utf-8-sig"

    if not response.text.strip():
        # /json-nextchants returns a response with text='\r\n' in situations where
        # there are no suggested chants
        return None

    parsed_response = response.json()

    if not isinstance(parsed_response, (dict, list)):
        return None

    return parsed_response
