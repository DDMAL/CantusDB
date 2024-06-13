"""
A collection of functions for fetching data from
Cantus Index's (CI's) various APIs.
"""

import requests
from typing import Optional, Union, Callable
from main_app.models import Genre
import json
from requests.exceptions import SSLError, Timeout

CANTUS_INDEX_DOMAIN: str = "https://cantusindex.uwaterloo.ca"
DEFAULT_TIMEOUT: float = 2  # seconds
NUMBER_OF_SUGGESTED_CHANTS: int = 3  # this number can't be too large,
# since for each suggested chant, we make a request to Cantus Index.
# We haven't yet parallelized this process, so setting this number
# too high will cause the Chant Create page to take a very long time
# to load. If/when we parallelize this process, we want to limit
# the size of the burst of requests sent to CantusIndex.


def get_suggested_chants(
    cantus_id: str, number_of_suggestions: int = NUMBER_OF_SUGGESTED_CHANTS
) -> Optional[list[dict]]:
    endpoint_path: str = f"/json-nextchants/{cantus_id}"
    all_suggestions: Union[list, dict, None] = get_json_from_ci_api(endpoint_path)

    if not isinstance(all_suggestions, list):
        # get_json_from_ci_api timed out
        # or CI returned a response with no suggestions.
        return None

    # when Cantus ID doesn't exist within CI, CI's api returns a 200 response with `['Cantus ID is not valid']`
    first_suggestion = all_suggestions[0]
    if not isinstance(first_suggestion, dict):
        return None

    sort_by_occurrences: Callable[[dict], int] = lambda suggestion: int(
        suggestion["count"]
    )
    sorted_suggestions: list = sorted(
        all_suggestions, key=sort_by_occurrences, reverse=True
    )
    trimmed_suggestions: list = sorted_suggestions[:number_of_suggestions]

    suggested_chants: list[Optional[dict]] = []
    for suggestion in trimmed_suggestions:
        cantus_id: str = suggestion["cid"]
        occurrences: int = int(suggestion["count"])
        suggested_chants.append(get_suggested_chant(cantus_id, occurrences))

    # filter out Cantus IDs where get_suggested_chant timed out
    filtered_suggestions: list[dict] = [
        sugg for sugg in suggested_chants if sugg is not None
    ]

    return filtered_suggestions


def get_suggested_chant(
    cantus_id: str, occurrences: int, timeout: float = DEFAULT_TIMEOUT
) -> Optional[dict]:
    """Given a Cantus ID and a number of occurrences, query one of Cantus Index's
    APIs for information on that Cantus ID and return a dictionary
    containing a full text, an incipit, the ID of that Cantus ID's genre, and
    the number of occurrences for that Cantus ID

    (Number of occurrences: this function is used on the Chant Create page,
    to suggest Cantus IDs of chants that might follow a chant with the Cantus ID
    of the most recently created chant within the current source. Number of occurrences
    is provided by Cantus Index's /nextchants API, based on which chants follow which
    other chants in existing manuscripts)

    Args:
        cantus_id (str): a Cantus ID
        occurrences (int): the number of times chants with this Cantus ID follow chants
            with the Cantus ID of the most recently created chant.

    Returns:
        Optional[dict]: A dictionary with the following keys:
            - "cantus_id"
            - "occurrences"
            - "fulltext"
            - "incipit"
            - "genre_id"
            ...but if get_json_from_ci_api timed out, returns None instead
    """
    endpoint_path: str = f"/json-cid/{cantus_id}"
    json: Union[dict, list, None] = get_json_from_ci_api(endpoint_path, timeout=timeout)

    if not isinstance(json, dict):
        # mostly, in case of a timeout within get_json_from_ci_api
        return None

    try:
        fulltext: str = json["info"]["field_full_text"]
        incipit: str = " ".join(fulltext.split(" ")[:5])
        genre_name: str = json["info"]["field_genre"]
    except TypeError:
        return None
    genre_id: Optional[int] = None
    try:
        genre_id = Genre.objects.get(name=genre_name).id
    except Genre.DoesNotExist:
        pass

    clean_cantus_id = cantus_id.replace(".", "d").replace(":", "c")
    #                                        "d"ot             "c"olon
    return {
        "cantus_id": cantus_id,
        "occurrences": occurrences,
        "fulltext": fulltext,
        "incipit": incipit,
        "genre_name": genre_name,
        "genre_id": genre_id,
        "clean_cantus_id": clean_cantus_id,
    }


def get_suggested_fulltext(cantus_id: str) -> Optional[str]:
    endpoint_path: str = f"/json-cid/{cantus_id}"
    json: Union[dict, list, None] = get_json_from_ci_api(endpoint_path)

    if not isinstance(json, dict):
        # mostly, in case of a timeout within get_json_from_ci_api
        return None

    try:
        suggested_fulltext = json["info"]["field_full_text"]
    except KeyError:
        return None

    return suggested_fulltext


def get_merged_cantus_ids() -> Optional[list]:
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
    uri: str = f"https://cantusindex.org{endpoint_path}"
    try:
        response: requests.Response = requests.get(uri, timeout=DEFAULT_TIMEOUT)
    except requests.exceptions.Timeout:
        return None
    if not response.status_code == 200:
        return None
    response.encoding = "utf-8-sig"
    raw_text: str = response.text
    text_without_bom: str = raw_text.encode().decode("utf-8-sig")
    merge_events: list = json.loads(text_without_bom)

    if not isinstance(merge_events, list):
        return None
    return merge_events


def get_ci_text_search(search_term: str) -> Optional[list[Optional[dict]]]:
    """Fetch data from Cantus Index for a given search term.
    To do a text search on CI, use 'https://cantusindex.org/json-text/<text to search>
    """

    # We have to use the old CI domain since the API is still not available on
    # cantusindex.uwaterloo.ca. Once it's available, we can use get_json_from_ci_api
    # json: Union[dict, list, None] = get_json_from_ci_api(uri)
    uri: str = f"https://cantusindex.org/json-text/{search_term}"
    try:
        response: requests.Response = requests.get(
            uri,
            timeout=DEFAULT_TIMEOUT,
        )
    except (SSLError, Timeout, requests.HTTPError) as exc:
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
) -> Union[dict, list, None]:
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
            In case the request times out, returns None.
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

    return response.json()
