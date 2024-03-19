import csv
from typing import Optional, Union
from django.db.models.query import QuerySet
from django.http.response import JsonResponse
from django.http import HttpResponse, HttpResponseNotFound
from django.utils.http import urlencode
from django.shortcuts import render, redirect
from django.urls.base import reverse
from articles.models import Article
from main_app.models import (
    Century,
    Chant,
    Differentia,
    Feast,
    Genre,
    Notation,
    Office,
    Provenance,
    RismSiglum,
    Segment,
    Sequence,
    Source,
)
from django.contrib.auth.decorators import login_required, user_passes_test
from main_app.models.base_model import BaseModel
from next_chants import next_chants
from django.contrib import messages
from django.http import Http404
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied, BadRequest
from django.urls import reverse
from django.contrib.auth import get_user_model
from typing import List
from django.core.paginator import Paginator
from django.templatetags.static import static
from django.contrib.flatpages.models import FlatPage
from dal import autocomplete
from django.db.models import Q
from django.shortcuts import get_object_or_404


@login_required
def items_count(request):
    """
    Function-based view for the ``items count`` page, accessed with ``content-statistics``

    Update 2022-01-05:
    This page has been changed on the original Cantus. It is now in the private domain

    Args:
        request (request): The request

    Returns:
        HttpResponse: Render the page
    """
    # in items count, the number on old cantus shows the total count of a type of object (chant, seq)
    # no matter published or not
    # but for the count of sources, it only shows the count of published sources
    chant_count = Chant.objects.count()
    sequence_count = Sequence.objects.count()
    source_count = Source.objects.filter(published=True).count()

    context = {
        "chant_count": chant_count,
        "sequence_count": sequence_count,
        "source_count": source_count,
    }
    return render(request, "items_count.html", context)


def ajax_concordance_list(request, cantus_id):
    """
    Function-based view responding to the AJAX call for concordance list on the chant detail page,
    accessed with ``chants/<int:pk>``, click on "Display concordances of this chant"

    Args:
        cantus_id (str): The Cantus ID of the requested concordances group

    Returns:
        JsonResponse: A response to the AJAX call, to be unpacked by the frontend js code
    """
    chants = Chant.objects.filter(cantus_id=cantus_id)
    seqs = Sequence.objects.filter(cantus_id=cantus_id)

    display_unpublished = request.user.is_authenticated
    if not display_unpublished:
        chants = chants.filter(source__published=True)
        seqs = seqs.filter(source__published=True)

    if seqs:
        chants = chants.union(seqs).order_by("siglum", "folio")
    else:
        chants = chants.order_by("siglum", "folio")
    # queryset(list of dictionaries)
    concordance_values = chants.values(
        "siglum",
        "folio",
        "incipit",
        "office__name",
        "genre__name",
        "position",
        "feast__name",
        "mode",
        "image_link",
    )

    concordances = list(concordance_values)
    for i, concordance in enumerate(concordances):
        # some chants do not have a source
        # for those chants, do not return source link
        if chants[i].source:
            concordance["source_link"] = chants[i].source.get_absolute_url()
        if chants[i].search_vector:
            concordance["chant_link"] = chants[i].get_absolute_url()
        else:
            concordance["chant_link"] = reverse("sequence-detail", args=[chants[i].id])
        concordance["db"] = "CD"

    concordance_count = len(concordances)
    return JsonResponse(
        {"concordances": concordances, "concordance_count": concordance_count},
        safe=True,
    )


def ajax_melody_list(request, cantus_id) -> JsonResponse:
    """
    Function-based view responding to the AJAX call for melody list on the chant detail page,
    accessed with ``chants/<int:pk>``, click on "Display melodies connected with this chant"

    Args:
        cantus_id (str): The Cantus ID of the requested concordances group

    Returns:
        JsonResponse: A response to the AJAX call, to be unpacked by the frontend js code
    """
    chants: QuerySet[Chant] = (
        Chant.objects.filter(cantus_id=cantus_id).exclude(volpiano=None).order_by("id")
    )

    display_unpublished: bool = request.user.is_authenticated
    if not display_unpublished:
        chants = chants.filter(source__published=True)

    concordance_values: QuerySet[dict] = chants.values(
        "source__siglum",
        "folio",
        "office__name",
        "genre__name",
        "position",
        "feast__name",
        "cantus_id",
        "volpiano",
        "mode",
        # OldCantus seems to use whichever is present: ms spelling, std spelling, incipit (in that order)
        "manuscript_full_text_std_spelling",
    )

    concordances: list[dict] = list(concordance_values)
    for i, concordance in enumerate(concordances):
        # we need to use each chant's _source_'s siglum, and not the
        # legacy sigla that were attached to chants in OldCantus
        concordance["siglum"] = concordance.pop("source__siglum")
        # for chants that do not have a source, do not attempt
        # to return a source link
        if chants[i].source:
            concordance["source_link"] = chants[i].source.get_absolute_url()
        concordance["ci_link"] = chants[i].get_ci_url()
        concordance["chant_link"] = chants[i].get_absolute_url()
        concordance["db"] = "CD"

    concordance_count: int = len(concordances)
    return JsonResponse(
        {"concordances": concordances, "concordance_count": concordance_count},
        safe=True,
    )


def csv_export(request, source_id):
    """
    Function-based view for the CSV export page, accessed with ``csv/<str:source_id>``

    Args:
        source_id (str): The ID of the source to export

    Returns:
        HttpResponse: The CSV response
    """
    try:
        source = Source.objects.get(id=source_id)
    except:
        raise Http404("This source does not exist")

    display_unpublished = request.user.is_authenticated

    if (not source.published) and (not display_unpublished):
        raise PermissionDenied

    # "4064" is the segment id of the sequence DB, sources in that segment have sequences instead of chants
    if source.segment and source.segment.id == 4064:
        entries = source.sequence_set.order_by("id")
    else:
        entries = source.chant_set.order_by("id").select_related(
            "feast", "office", "genre"
        )

    response = HttpResponse(content_type="text/csv")
    # response["Content-Disposition"] = 'attachment; filename="somefilename.csv"'

    writer = csv.writer(response)
    writer.writerow(
        [
            "siglum",
            "marginalia",
            "folio",
            "sequence",
            "incipit",
            "feast",
            "office",
            "genre",
            "position",
            "cantus_id",
            "mode",
            "finalis",
            "differentia",
            "differentiae_database",
            "fulltext_standardized",
            "fulltext_ms",
            "volpiano",
            "image_link",
            "melody_id",
            "addendum",
            "extra",
            "node_id",
        ]
    )
    for entry in entries:
        feast = entry.feast.name if entry.feast else ""
        office = entry.office.name if entry.office else ""
        genre = entry.genre.name if entry.genre else ""
        diff_db = entry.diff_db.id if entry.diff_db else ""

        writer.writerow(
            [
                entry.siglum,
                entry.marginalia,
                entry.folio,
                # if entry has a c_sequence, it's a Chant. If it doesn't, it's a Sequence, so write its s_sequence
                entry.c_sequence if entry.c_sequence is not None else entry.s_sequence,
                entry.incipit,
                feast,
                office,
                genre,
                entry.position,
                entry.cantus_id,
                entry.mode,
                entry.finalis,
                entry.differentia,
                entry.diff_db,
                entry.manuscript_full_text_std_spelling,
                entry.manuscript_full_text,
                entry.volpiano,
                entry.image_link,
                entry.melody_id,
                entry.addendum,
                entry.extra,
                entry.id,
            ]
        )

    return response


def csv_export_redirect_from_old_path(request, source_id):
    return redirect(reverse("csv-export", args=[source_id]))


def contact(request):
    """
    Function-based view that renders the contact page ``contact``

    Args:
        request (request): The request

    Returns:
        HttpResponse: Render the contact page
    """
    return render(request, "contact.html")


def ajax_melody_search(request):
    """
    Function-based view responding to melody search AJAX calls, accessed with ``melody``

    The queryset is filtered according to the ``GET`` parameters

    ``GET`` parameters:
        ``notes``: Note sequence drawn on the canvas by the user
        ``anywhere``: Bool value indicating either "search anywhere" or "search beginning"
        ``transpose``: Bool value indicating either "search exact matches" or "search transpositions"
        ``siglum``: Filters by the siglum
        ``text``: Filters by the chant text
        ``genre_name``: Filters by genre of chant
        ``feast_name``: Filters by feast of chant
        ``mode``: Filters by mode of Chant
        ``source``: Search in a specific source

    Args:
        request (request): The request

    Returns:
        JsonResponse: A response to the AJAX call, to be unpacked by frontend js code
    """
    # all search parameters are passed in as GET params, without using the url conf
    notes = request.GET.get("notes")
    anywhere = request.GET.get("anywhere")
    transpose = request.GET.get("transpose")
    siglum = request.GET.get("siglum")
    text = request.GET.get("text")
    genre_name = request.GET.get("genre")
    feast_name = request.GET.get("feast")
    mode = request.GET.get("mode")
    source = request.GET.get("source")

    display_unpublished = request.user.is_authenticated
    if not display_unpublished:
        chants = Chant.objects.filter(source__published=True)
    else:
        chants = Chant.objects

    # if "search exact matches + transpositions"
    if transpose == "true":
        # calculate intervals
        # replace '9' (the note G) with the char corresponding to (ASCII(a) - 1), because 'a' denotes the note A
        notes_copy = list(notes.replace("9", chr(ord("a") - 1)))
        # we model the interval between notes using the difference between the ASCII codes of corresponding letters
        # the letter for the note B is "j" (106), note A is "h" (104), the letter "i" (105) is skipped
        # move all notes above A down by one letter
        for j, note in enumerate(notes_copy):
            if ord(note) >= 106:
                notes_copy[j] = chr(ord(note) - 1)
        # `intervals` records the difference between two adjacent notes
        intervals = "".join(
            [
                str(ord(notes_copy[j]) - ord(notes_copy[j - 1]))
                for j in range(1, len(notes_copy))
            ]
        )
        # if "search anywhere in the melody"
        if anywhere == "true":
            chants = chants.filter(volpiano_intervals__contains=intervals)
        # if "search the beginning of melody"
        else:
            chants = chants.filter(volpiano_intervals__startswith=intervals)
    # if "search exact matches"
    else:
        # if "search anywhere in the melody"
        if anywhere == "true":
            chants = chants.filter(volpiano_notes__contains=notes)
        # if "search the beginning of melody"
        else:
            chants = chants.filter(volpiano_notes__startswith=notes)

    # filter the queryset with search params

    # source id and siglum are duplicate information, they both uniquely identify a source
    # if searching in a specific source, use `source`
    # if searching across all sources, use `siglum`
    if source:
        chants = chants.filter(source__id=source)
    elif siglum:
        chants = chants.filter(siglum__icontains=siglum)

    if text:
        chants = chants.filter(manuscript_full_text_std_spelling__icontains=text)
    if genre_name:
        chants = chants.filter(genre__name__icontains=genre_name)
    if feast_name:
        chants = chants.filter(feast__name__icontains=feast_name)
    if mode:
        chants = chants.filter(mode__icontains=mode)

    result_values = chants.order_by("id").values(
        "id",
        "siglum",
        "folio",
        "incipit",
        "genre__name",
        "feast__name",
        "mode",
        "volpiano",
    )
    # convert queryset to a list of dicts because QuerySet is not JSON serializable
    # the above constructed queryset will be evaluated here
    results = list(result_values)
    for result in results:
        # construct the url for chant detail page and add it to the result
        result["chant_link"] = reverse("chant-detail", args=[result["id"]])

    result_count = result_values.count()
    return JsonResponse({"results": results, "result_count": result_count}, safe=True)


def ajax_search_bar(request, search_term):
    """
    Function-based view responding to global search bar AJAX calls,
    accessed with the search bar on the top-right corner of almost every page.

    Args:
        search_term (str): The search term input

    Returns:
        JsonResponse: A response to the AJAX call, to be unpacked by frontend js code
    """
    # load only the first seven chants
    CHANT_CNT: int = 7

    chants: QuerySet[Chant]
    if any(map(str.isdigit, search_term)):
        # if the search term contains at least one digit, assume user is searching by Cantus ID
        chants = Chant.objects.filter(cantus_id__istartswith=search_term).order_by("id")
    else:
        # if the search term does not contain any digits, assume user is searching by incipit
        chants = Chant.objects.filter(incipit__istartswith=search_term).order_by("id")

    display_unpublished: bool = request.user.is_authenticated
    if not display_unpublished:
        chants = chants.filter(source__published=True)

    chants = chants[:CHANT_CNT]

    returned_values: list[dict] = list(
        chants.values(
            "id",  # not used in the js, but used to calculate chant_link below
            "incipit",
            "genre__name",
            "feast__name",
            "cantus_id",
            "mode",
            "source__siglum",
            "office__name",
            "folio",
            "c_sequence",
        )
    )
    for values_for_chant in returned_values:
        chant_link = reverse("chant-detail", args=[values_for_chant["id"]])
        values_for_chant["chant_link"] = chant_link
    return JsonResponse({"chants": returned_values}, safe=True)


def json_melody_export(request, cantus_id: str) -> JsonResponse:
    chants = Chant.objects.filter(
        cantus_id=cantus_id, volpiano__isnull=False, source__published=True
    )

    db_keys = [
        "melody_id",
        "id",
        "cantus_id",
        "siglum",
        "source__id",  # don't fetch the entire Source object, just the id of
        # the source. __id is removed in standardize_for_api below
        "folio",
        "incipit",
        "manuscript_full_text",
        "volpiano",
        "mode",
        "feast__id",
        "office__id",
        "genre__id",
        "position",
    ]

    chants_values = list(chants.values(*db_keys))  # a list of dictionaries. Each
    # dictionary represents metadata on one chant

    standardized_chants_values = [
        standardize_dict_for_json_melody_export(cv, request) for cv in chants_values
    ]

    return JsonResponse(standardized_chants_values, safe=False)


def standardize_dict_for_json_melody_export(
    chant_values: List[dict], request
) -> List[dict]:
    """Take a list of dictionaries, and in each dictionary, change several
    of the keys to match their values in OldCantus

    Args:
        chant_values (List[dict]): a list of dictionaries, each containing
            information on a single chant in the database
        request: passed when this is called in json_melody_export. Used to get the domain
            while building the chant links

    Returns:
        List[dict]: a list of dictionaries, with updated keys
    """
    keymap = {  # map attribute names from Chant model (i.e. db_keys
        # in json_melody_export) to corresponding attribute names
        # in old API, and remove artifacts of query process (i.e. __id suffixes)
        "melody_id": "mid",  #                  <-
        "id": "nid",  #                         <-
        "cantus_id": "cid",  #                  <-
        "siglum": "siglum",
        "source__id": "srcnid",  #              <-
        "folio": "folio",
        "incipit": "incipit",
        "manuscript_full_text": "fulltext",  #  <-
        "volpiano": "volpiano",
        "mode": "mode",
        "feast__id": "feast",  #                <-
        "office__id": "office",  #              <-
        "genre__id": "genre",  #                <-
        "position": "position",
    }

    standardized_chant_values = {keymap[key]: chant_values[key] for key in chant_values}

    # manually build a couple of last fields that aren't represented in Chant object
    chant_uri = request.build_absolute_uri(
        reverse("chant-detail", args=[chant_values["id"]])
    )
    standardized_chant_values["chantlink"] = chant_uri
    src_uri = request.build_absolute_uri(
        reverse("source-detail", args=[chant_values["source__id"]])
    )
    standardized_chant_values["srclink"] = src_uri

    return standardized_chant_values


def json_sources_export(request) -> JsonResponse:
    """
    Generate a json object of published sources with their IDs and CSV links
    """
    cantus_segment = Segment.objects.get(id=4063)
    sources = cantus_segment.source_set.filter(published=True)
    ids = [source.id for source in sources]

    csv_links = {id: build_json_sources_export_dictionary(id, request) for id in ids}

    return JsonResponse(csv_links)


def build_json_sources_export_dictionary(id: int, request) -> dict:
    """Return a dictionary containing a link to the csv-export page for a source

    Args:
        id (int): the pk of the source
        request: passed when this is called in json_sources_export. Used to get the domain
            while building the CSV link

    Returns:
        dict: a dictionary with a single key, "csv", and a link to the source's csv-export
            page
    """
    return {"csv": request.build_absolute_uri(reverse("csv-export", args=[id]))}


def json_nextchants(request, cantus_id):
    ids_and_counts = next_chants(cantus_id, display_unpublished=False)
    suggested_chants_dict = {id: count for (id, count) in ids_and_counts}
    return JsonResponse(suggested_chants_dict)


def json_cid_export(request, cantus_id: str) -> JsonResponse:
    """Return a JsonResponse containing information on all chants with a given
    Cantus ID, in the following format:
    {
        "chants": [
            {
                "chant": {
                    a bunch of keys and values, created in build_json_cid_dictionary
                },
            },
            {
                "chant": {
                    etc.
                },
            },
        ]
    }
    We believe Cantus Index uses this API in building its list of concordances
    for a given Cantus ID across the databases in the Cantus Network

    Args:
        request: the incoming request
        cantus_id (string): A Cantus ID
    """

    # the API in OldCantus appears to only return chants, and no sequences.
    chants = Chant.objects.filter(cantus_id=cantus_id).filter(source__published=True)
    chant_dicts = [{"chant": build_json_cid_dictionary(c, request)} for c in chants]
    response = {"chants": chant_dicts}
    return JsonResponse(response)


def build_json_cid_dictionary(chant, request) -> dict:
    """Return a dictionary with information on a given chant in the database

    Args:
        chant: a Chant
        request: passed when this is called in json_cid_export. Used to get the domain
            while building the chant link

    Returns:
        dict: a dictionary with information about the chant and its source, including
            absolute URLs for the chant and source detail pages
    """
    source_relative_url = reverse("source-detail", args=[chant.source.id])
    source_absolute_url = request.build_absolute_uri(source_relative_url)
    chant_relative_url = reverse("chant-detail", args=[chant.id])
    chant_absolute_url = request.build_absolute_uri(chant_relative_url)
    dictionary = {
        "siglum": chant.source.siglum,
        "srclink": source_absolute_url,
        "chantlink": chant_absolute_url,
        "folio": chant.folio if chant.folio else "",
        "sequence": chant.c_sequence if chant.c_sequence else 0,
        "incipit": chant.incipit if chant.incipit else "",
        "feast": chant.feast.name if chant.feast else "",
        "genre": chant.genre.name if chant.genre else "",
        "office": chant.office.name if chant.office else "",
        "position": chant.position if chant.position else "",
        "cantus_id": chant.cantus_id if chant.cantus_id else "",
        "image": chant.image_link if chant.image_link else "",
        "mode": chant.mode if chant.mode else "",
        "full_text": (
            chant.manuscript_full_text_std_spelling
            if chant.manuscript_full_text_std_spelling
            else ""
        ),
        "melody": chant.volpiano if chant.volpiano else "",
        "db": "CD",
    }
    return dictionary


def record_exists(rec_type: BaseModel, pk: int) -> bool:
    """Determines whether record of specific type (chant, source, sequence, article) exists for a given pk

    Args:
        rec_type (BaseModel): Which model to check to see if an object of that type exists
        pk (int): The ID of the object being checked for.

    Returns:
        bool: True if an object of the specified model with the specified ID exists, False otherwise.
    """
    try:
        rec_type.objects.get(id=pk)
        return True
    except rec_type.DoesNotExist:
        return False


def get_user_id_from_old_indexer_id(pk: int) -> Optional[int]:
    """
    Finds the matching User ID in NewCantus for an Indexer ID in OldCantus.
    This is stored in the User table's old_indexer_id column.
    This is necessary because indexers were originally stored in the general Node
    table in OldCantus, but are now represented as users in NewCantus.

    Args:
        pk (int): the ID of an indexer in OldCantus

    Returns:
        Optional int: the ID of the corresponding User in NewCantus
    """
    User = get_user_model()
    try:
        result = User.objects.get(old_indexer_id=pk)
        return result.id
    except User.DoesNotExist:
        return None


def check_for_unpublished(item: Union[Chant, Sequence, Source]) -> None:
    """Raises an Http404 exception if item is unpublished

    Args:
        item (Chant, Sequence, or Source): An item to check whether it is published or not

    Raises:
        Http404 if the item is a source and it's unpublished,
            or if it's a chant/sequence and its source is unpublished

    Returns:
        None
    """
    if isinstance(item, Source):
        if not item.published:
            raise Http404()
    if isinstance(item, Chant) or isinstance(item, Sequence):
        if not item.source.published:
            raise Http404()


NODE_TYPES_AND_VIEWS = [
    (Chant, "chant-detail"),
    (Source, "source-detail"),
    (Sequence, "sequence-detail"),
    (Article, "article-detail"),
]


# all IDs above this value are created in NewCantus and thus could have conflicts between types.
# when data is migrated from OldCantus to NewCantus, (unpublished) dummy objects are created
# in the database to ensure that all newly created objects have IDs above this number.
NODE_ID_CUTOFF = 1_000_000


def json_node_export(request, id: int) -> JsonResponse:
    """
    returns all fields of the chant/sequence/source/indexer with the specified `id`
    """

    # all IDs above this value are created in NewCantus and thus could have conflicts between types.
    # when data is migrated from OldCantus to NewCantus, (unpublished) dummy objects are created
    # in the database to ensure that all newly created objects have IDs above this number.
    if id >= NODE_ID_CUTOFF:
        raise Http404()

    user_id = get_user_id_from_old_indexer_id(id)
    if get_user_id_from_old_indexer_id(id) is not None:
        User = get_user_model()
        user = User.objects.filter(id=user_id)
        # in order to easily unpack the object's properties in `vals` below, `user` needs to be
        # a queryset rather than an individual object.
        vals = dict(*user.values())
        return JsonResponse(vals)

    for rec_type, _ in NODE_TYPES_AND_VIEWS:
        if record_exists(rec_type, id):
            requested_item = rec_type.objects.filter(id=id)
            # in order to easily unpack the object's properties in `vals` below, `requested_item`
            # needs to be a queryset rather than an individual object. But in order to
            # `check_for_unpublished`, we need a single object rather than a queryset, hence
            # `.first()`
            check_for_unpublished(
                requested_item.first()
            )  # raises a 404 if item is unpublished
            vals = dict(*requested_item.values())
            return JsonResponse(vals)

    return HttpResponseNotFound()


def notation_json_export(request, id: int) -> JsonResponse:
    """
    Return JsonResponse containing several key:value pairs
    for the notation with the specified ID
    """

    notation: Notation = get_object_or_404(Notation, id=id)

    data = {
        "id": notation.id,
        "name": notation.name,
        "date_created": notation.date_created,
        "date_updated": notation.date_updated,
        "created_by": notation.created_by_id,
        "last_updated_by": notation.last_updated_by_id,
    }

    return JsonResponse(data)


def provenance_json_export(request, id: int) -> JsonResponse:
    """
    Return JsonResponse containing several key:value pairs
    for the provenance with the specified ID
    """

    provenance: Provenance = get_object_or_404(Provenance, id=id)

    data = {
        "id": provenance.id,
        "name": provenance.name,
        "date_created": provenance.date_created,
        "date_updated": provenance.date_updated,
        "created_by": provenance.created_by_id,
        "last_updated_by": provenance.last_updated_by_id,
    }

    return JsonResponse(data)


def articles_list_export(request) -> HttpResponse:
    """Returns a list of URLs of all articles on the site

    Args:
        request: the incoming request

    Returns:
        HttpResponse: A list of URLs, separated by newline characters
    """
    articles = Article.objects.all()
    article_urls = [
        request.build_absolute_uri(reverse("article-detail", args=[article.id]))
        for article in articles
    ]
    return HttpResponse(" ".join(article_urls), content_type="text/plain")


def flatpages_list_export(request) -> HttpResponse:
    """Returns a list of URLs of all articles on the site

    Args:
        request: the incoming request

    Returns:
        HttpResponse: A list of URLs, separated by newline characters
    """

    flatpages = FlatPage.objects.all()
    flatpage_urls = [
        request.build_absolute_uri(flatpage.get_absolute_url())
        for flatpage in flatpages
    ]
    return HttpResponse(" ".join(flatpage_urls), content_type="text/plain")


def redirect_node_url(request, pk: int) -> HttpResponse:
    """
    A function that will redirect /node/ URLs from OldCantus to their corresponding page in NewCantus.
    This makes NewCantus links backwards compatible for users who may have bookmarked these types of URLs in OldCantus.
    In addition, this function (paired with get_user_id() below) account for the different numbering systems in both versions of CantusDB, notably for /indexer/ paths which are now at /user/.

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


@login_required
def change_password(request):
    if request.method == "POST":
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Your password was successfully updated!")
    else:
        form = PasswordChangeForm(request.user)
    return render(request, "registration/change_password.html", {"form": form})


def project_manager_check(user):
    """
    A callback function that will be called by the user_passes_test decorator of content_overview.

    Takes in a logged-in user as an argument.
    Returns True if they are in a "project manager" group, raises PermissionDenied otherwise.
    """
    if user.groups.filter(name="project manager").exists():
        return True
    raise PermissionDenied


# first give the user a chance to login
@login_required
# if they're logged in but they're not a project manager, raise 403
@user_passes_test(project_manager_check)
def content_overview(request):
    objects = []
    models = [
        Source,
        Chant,
        Feast,
        Sequence,
        Office,
        Provenance,
        Genre,
        Notation,
        Century,
        RismSiglum,
    ]

    model_names = [model._meta.verbose_name_plural for model in models]
    selected_model_name = request.GET.get("model", None)
    selected_model = None
    if selected_model_name in model_names:
        selected_model = models[model_names.index(selected_model_name)]

    objects = []
    if selected_model:
        objects = selected_model.objects.all().order_by("-date_updated")

    paginator = Paginator(objects, 100)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "models": model_names,
        "selected_model_name": selected_model_name,
        "page_obj": page_obj,
    }

    return render(request, "content_overview.html", context)


def redirect_indexer(request, pk: int) -> HttpResponse:
    """
    A function that will redirect /indexer/ URLs from OldCantus to their corresponding /user/ page in NewCantus.
    This makes NewCantus links backwards compatible for users who may have bookmarked these types of URLs in OldCantus.

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
    except KeyError:
        raise Http404
    return redirect(new_path)


def redirect_chant_list(request) -> HttpResponse:
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


class CurrentEditorsAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return get_user_model().objects.none()
        qs = (
            get_user_model()
            .objects.filter(
                Q(groups__name="project manager")
                | Q(groups__name="editor")
                | Q(groups__name="contributor")
            )
            .order_by("full_name")
        )
        if self.q:
            qs = qs.filter(
                Q(full_name__istartswith=self.q) | Q(email__istartswith=self.q)
            )
        return qs


class AllUsersAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return get_user_model().objects.none()
        qs = get_user_model().objects.all().order_by("full_name")
        if self.q:
            qs = qs.filter(
                Q(full_name__istartswith=self.q) | Q(email__istartswith=self.q)
            )
        return qs


class CenturyAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Century.objects.none()
        qs = Century.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs


class RismSiglumAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return RismSiglum.objects.none()
        qs = RismSiglum.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(name__istartswith=self.q)
        return qs


class FeastAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Feast.objects.none()
        qs = Feast.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class OfficeAutocomplete(autocomplete.Select2QuerySetView):
    def get_result_label(self, office):
        return f"{office.name} - {office.description}"

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Office.objects.none()
        qs = Office.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(
                Q(name__istartswith=self.q) | Q(description__icontains=self.q)
            )
        return qs


class GenreAutocomplete(autocomplete.Select2QuerySetView):
    def get_result_label(self, genre):
        return f"{genre.name} - {genre.description}"

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Genre.objects.none()
        qs = Genre.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(
                Q(name__istartswith=self.q) | Q(description__icontains=self.q)
            )
        return qs


class DifferentiaAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Differentia.objects.none()
        qs = Differentia.objects.all().order_by("differentia_id")
        if self.q:
            qs = qs.filter(differentia_id__istartswith=self.q)
        return qs


class ProvenanceAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Provenance.objects.none()
        qs = Provenance.objects.all().order_by("name")
        if self.q:
            qs = qs.filter(name__icontains=self.q)
        return qs


class ProofreadByAutocomplete(autocomplete.Select2QuerySetView):
    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return get_user_model().objects.none()
        qs = (
            get_user_model()
            .objects.filter(
                Q(groups__name="project manager") | Q(groups__name="editor")
            )
            .distinct()
            .order_by("full_name")
        )
        if self.q:
            qs = qs.filter(
                Q(full_name__istartswith=self.q) | Q(email__istartswith=self.q)
            )
        return qs
