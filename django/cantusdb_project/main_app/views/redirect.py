from typing import Optional

from django.shortcuts import redirect
from django.urls.base import reverse
from django.http import HttpResponse, Http404, HttpRequest
from django.templatetags.static import static
from django.core.exceptions import BadRequest
from django.utils.http import urlencode

from main_app.views.api import (
    NODE_TYPES_AND_VIEWS,
    record_exists,
    NODE_ID_CUTOFF,
    get_user_id_from_old_indexer_id,
)


def csv_export_redirect_from_old_path(request, source_id):
    return redirect(reverse("csv-export", args=[source_id]))


def redirect_node_url(request, pk: int) -> HttpResponse:
    """
    A function that will redirect /node/ URLs from OldCantus to their
    corresponding page in NewCantus. This makes NewCantus links backwards
    compatible for users who may have bookmarked these types of URLs in OldCantus.
    In addition, this function (paired with get_user_id() below) account for the
    different numbering systems in both versions of CantusDB, notably for /indexer/
    paths which are now at /user/.

    Takes in a request and the primary key (ID following /node/ in the URL) as arguments.
    Returns the matching page in NewCantus if it exists and a 404 otherwise.
    """

    if pk >= NODE_ID_CUTOFF:
        raise Http404("Invalid ID for /node/ path.")

    user_id = get_user_id_from_old_indexer_id(pk)
    if get_user_id_from_old_indexer_id(pk) is not None:
        return redirect("user-detail", user_id)

    for rec_type, view in NODE_TYPES_AND_VIEWS:
        if record_exists(rec_type, pk):
            # if an object is found, a redirect() call to the appropriate view is returned
            return redirect(view, pk)

    # if it reaches the end of the types with finding an existing object, a 404 will be returned
    raise Http404("No record found matching the /node/ query.")


def redirect_indexer(request, pk: int) -> HttpResponse:
    """
    A function that will redirect /indexer/ URLs from OldCantus to
    their corresponding /user/ page in NewCantus.
    This makes NewCantus links backwards compatible for users who
    may have bookmarked these types of URLs in OldCantus.

    Takes in a request and the Indexer ID as arguments.
    Returns the matching User page in NewCantus if it exists and a 404 otherwise.
    """
    user_id = get_user_id_from_old_indexer_id(pk)
    if get_user_id_from_old_indexer_id(pk) is not None:
        return redirect("user-detail", user_id)

    raise Http404("No indexer found matching the query.")


def redirect_office(request) -> HttpResponse:
    """
    Redirects from office/ (à la OldCantus) to offices/ (à la NewCantus)

    Args:
        request

    Returns:
        HttpResponse
    """
    return redirect("office-list")


def redirect_genre(request) -> HttpResponse:
    """
    Redirects from genre/ (à la OldCantus) to genres/ (à la NewCantus)

    Args:
        request

    Returns:
        HttpResponse
    """
    return redirect("genre-list")


def redirect_search(request: HttpRequest) -> HttpResponse:
    """
    Redirects from search/ (à la OldCantus) to chant-search/ (à la NewCantus)

    Args:
        request

    Returns:
        HttpResponse
    """
    return redirect("chant-search", permanent=True)


def redirect_documents(request) -> HttpResponse:
    """Handle requests to old paths for various
    documents on OldCantus, returning an HTTP Response
    redirecting the user to the updated path

    Args:
        request: the request to the old path

    Returns:
        HttpResponse: response redirecting to the new path
    """
    mapping = {
        "/sites/default/files/documents/1. Quick Guide to Liturgy.pdf": static(
            "documents/1. Quick Guide to Liturgy.pdf"
        ),
        "/sites/default/files/documents/2. Volpiano Protocols.pdf": static(
            "documents/2. Volpiano Protocols.pdf"
        ),
        "/sites/default/files/documents/3. Volpiano Neumes for Review.docx": static(
            "documents/3. Volpiano Neumes for Review.docx"
        ),
        "/sites/default/files/documents/4. Volpiano Neume Protocols.pdf": static(
            "documents/4. Volpiano Neume Protocols.pdf"
        ),
        "/sites/default/files/documents/5. Volpiano Editing Guidelines.pdf": static(
            "documents/5. Volpiano Editing Guidelines.pdf"
        ),
        "/sites/default/files/documents/7. Guide to Graduals.pdf": static(
            "documents/7. Guide to Graduals.pdf"
        ),
        "/sites/default/files/HOW TO - manuscript descriptions-Nov6-20.pdf": static(
            "documents/HOW TO - manuscript descriptions-Nov6-20.pdf"
        ),
    }
    old_path = request.path
    try:
        new_path = mapping[old_path]
    except KeyError as exc:
        raise Http404 from exc
    return redirect(new_path)


def redirect_chants(request) -> HttpResponse:
    # in OldCantus, the Browse Chants page was accessed via
    # `/chants/?source=<source ID>`
    # This view redirects to `/source/<source ID>/chants` to
    # maintain backwards compatibility
    source_id: Optional[str] = request.GET.get("source")
    if source_id is None:
        # source parameter must be provided
        raise BadRequest("Source parameter must be provided")

    base_url: str = reverse("browse-chants", args=[source_id])

    # optional search params
    feast_id: Optional[str] = request.GET.get("feast")
    genre_id: Optional[str] = request.GET.get("genre")
    folio: Optional[str] = request.GET.get("folio")
    search_text: Optional[str] = request.GET.get("search_text")

    d: dict = {
        "feast": feast_id,
        "genre": genre_id,
        "folio": folio,
        "search_text": search_text,
    }
    params: dict = {k: v for k, v in d.items() if v is not None}

    query_string: str = urlencode(params)
    url: str = f"{base_url}?{query_string}" if query_string else base_url

    return redirect(url, permanent=True)


def redirect_source_inventory(request) -> HttpResponse:
    source_id: str = request.GET.get("source")
    if source_id is None:
        # source parameter must be provided
        raise BadRequest("Source parameter must be provided")
    url: str = reverse("source-inventory", args=[source_id])
    return redirect(url, permanent=True)
