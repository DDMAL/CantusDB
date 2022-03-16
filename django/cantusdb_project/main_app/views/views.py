import csv
from django.http.response import HttpResponseRedirect, JsonResponse
from django.http import HttpResponse
from django.shortcuts import render
from django.urls.base import reverse
from main_app.models import (
    Chant,
    Sequence,
    Source,
)
from main_app.forms import ContactForm
from django.core.mail import send_mail, get_connection


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
    # no matter public or not
    # but for the count of sources, it only shows the count of public sources
    chant_count = Chant.objects.count()
    sequence_count = Sequence.objects.count()
    source_count = Source.objects.filter(public=True).count()

    context = {
        "chant_count": chant_count,
        "sequence_count": sequence_count,
        "source_count": source_count,
    }
    return render(request, "items_count.html", context)


def ajax_concordance_list(request, cantus_id):
    """
    Function-based view responding to the AJAX call for concordance list on the chant detail page,
    accessed with ``chants/<ink:pk>``, click on "Display concordances of this chant"

    Args:
        cantus_id (str): The Cantus ID of the requested concordances group

    Returns:
        JsonResponse: A response to the AJAX call, to be unpacked by the frontend js code
    """
    chants = Chant.objects.filter(cantus_id=cantus_id)
    seqs = Sequence.objects.filter(cantus_id=cantus_id)
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


def ajax_melody_list(request, cantus_id):
    """
    Function-based view responding to the AJAX call for melody list on the chant detail page,
    accessed with ``chants/<ink:pk>``, click on "Display melodies connected with this chant"

    Args:
        cantus_id (str): The Cantus ID of the requested concordances group

    Returns:
        JsonResponse: A response to the AJAX call, to be unpacked by the frontend js code
    """
    chants = (
        Chant.objects.filter(cantus_id=cantus_id).exclude(volpiano=None).order_by("id")
    )

    # queryset(list of dictionaries)
    concordance_values = chants.values(
        "siglum",
        "folio",
        "office__name",
        "genre__name",
        "position",
        "feast__name",
        "cantus_id",
        "volpiano",
        "mode",
        # seems to use whichever is present: ms spelling, std spelling, incipit
        "manuscript_full_text_std_spelling",
    )

    concordances = list(concordance_values)
    for i, concordance in enumerate(concordances):
        # some chants do not have a source
        # for those chants, do not return source link
        if chants[i].source:
            concordance["source_link"] = chants[i].source.get_absolute_url()
        concordance["ci_link"] = chants[i].get_ci_url()
        concordance["chant_link"] = chants[i].get_absolute_url()
        concordance["db"] = "CD"

    concordance_count = len(concordances)
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
    source = Source.objects.get(id=source_id)
    # "4064" is the segment id of the sequence DB, sources in that segment has sequences instead of chants
    if source.segment.id == 4064:
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
            # "differentia_new",
            "fulltext_standardized",
            "fulltext_ms",
            "volpiano",
            "image_link",
            "melody_id",
            "cao_concordances",
            "addendum",
            "extra",
            "node_id",
        ]
    )
    for entry in entries:
        feast = entry.feast.name if entry.feast else ""
        office = entry.office.name if entry.office else ""
        genre = entry.genre.name if entry.genre else ""

        writer.writerow(
            [
                entry.siglum,
                entry.marginalia,
                entry.folio,
                entry.sequence_number,
                entry.incipit,
                feast,
                office,
                genre,
                entry.position,
                entry.cantus_id,
                entry.mode,
                entry.finalis,
                entry.differentia,
                # entry.differentia_new,
                entry.manuscript_full_text_std_spelling,
                entry.manuscript_full_text,
                entry.volpiano,
                entry.image_link,
                entry.melody_id,
                entry.cao_concordances,
                entry.addendum,
                entry.extra,
                entry.id,
            ]
        )

    return response


def contact_us(request):
    """
    Function-based view that renders a contact form, access with ``contact``

    Args:
        request (request): The request

    Returns:
        HttpResponse: Render the contact form
    """
    submitted = False
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data["name"]
            sender_email = form.cleaned_data["sender_email"]
            subject = form.cleaned_data["subject"]
            message = form.cleaned_data["message"]
            # when changing recipients into a real email address, write it as an env variable
            recipients = ["info@test.com"]

            connection = get_connection(
                "django.core.mail.backends.console.EmailBackend"
                # "django.core.mail.backends.smtp.EmailBackend"
            )
            send_mail(subject, message, sender_email, recipients, connection=connection)
            return HttpResponseRedirect("/contact?submitted=True")
    else:
        form = ContactForm()
        if request.GET.get("submitted"):
            submitted = True
    return render(request, "contact_form.html", {"form": form, "submitted": submitted})


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

    # only include public chants in the result
    chants = Chant.objects.filter(source__public=True, source__visible=True)

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
    chants = Chant.objects.filter(incipit__icontains=search_term).order_by("id")[0:7]
    returned_values = chants.values(
        "incipit",
        "genre__name",
        "feast__name",
        "cantus_id",
        "mode",
        "siglum",
        "office__name",
        "folio",
        "sequence_number",
    )
    returned_values = list(returned_values)
    for i in range(chants.count()):
        chant_link = chants[i].get_absolute_url()
        returned_values[i]["chant_link"] = chant_link
    return JsonResponse({"chants": returned_values}, safe=True)

