"""
A collection of functions for fetching data from
Cantus Index's (CI's) various APIs.
"""

import requests
from codecs import decode
from typing import Optional, Union
from main_app.models import Genre

CANTUS_INDEX_DOMAIN = "https://cantusindex.uwaterloo.ca"
DEFAULT_TIMEOUT = 2  # seconds
NUMBER_OF_SUGGESTED_CHANTS = 5  # this number can't be too large,
# since for each suggested chant, we make a request to Cantus Index.
# We haven't yet parallelized this process, so setting this number
# too high will cause the Chant Create page to take a very long time
# to load. If/when we parallelize this process, we want to limit
# the size of the burst of requests sent to CantusIndex.


def get_suggested_chants(
    cantus_id: str, number_of_suggestions: int = NUMBER_OF_SUGGESTED_CHANTS
) -> list[dict]:
    endpoint_path: str = f"/json-nextchants/{cantus_id}"
    all_suggestions: list = get_json_from_ci_api(endpoint_path)
    sort_by_occurrences: function = lambda suggestion: int(suggestion["count"])
    sorted_suggestions = sorted(all_suggestions, key=sort_by_occurrences, reverse=True)
    trimmed_suggestions = sorted_suggestions[:number_of_suggestions]

    suggested_chants: list[dict] = []
    for suggestion in trimmed_suggestions:
        cantus_id = suggestion["cid"]
        occurrences = suggestion["count"]
        suggested_chants.append(get_suggested_chant(cantus_id, occurrences))

    # filter out Cantus IDs where get_suggested_chant timed out
    filtered_suggestions = [sugg for sugg in suggested_chants if sugg is not None]

    return filtered_suggestions


def get_suggested_chant(cantus_id: str, occurrences: int) -> Optional[dict]:
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
    json: dict = get_json_from_ci_api(endpoint_path)

    if not json:  # mostly, in case of a timeout within get_json_from_ci_api
        return None

    fulltext: str = json["info"]["field_full_text"]
    incipit = " ".join(fulltext.split(" ")[:5])
    genre_name: str = json["info"]["field_genre"]
    genre: Genre = Genre.objects.get(name=genre_name)
    genre_id: int = genre.id

    return {
        "cantus_id": cantus_id,
        "occurrences": occurrences,
        "fulltext": fulltext,
        "incipit": incipit,
        "genre_id": genre_id,
    }


def get_json_from_ci_api(
    path: str, timeout: int = DEFAULT_TIMEOUT
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
        return {}

    response.encoding = "utf-8-sig"
    return response.json()
