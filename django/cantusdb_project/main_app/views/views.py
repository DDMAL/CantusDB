import csv
from django.http.response import HttpResponseRedirect, JsonResponse
from django.http import HttpResponse, HttpResponseNotFound
from django.shortcuts import render, redirect
from django.urls.base import reverse
from main_app.models import (
    Century,
    Chant,
    Feast,
    Genre,
    Indexer,
    Notation,
    Office,
    Provenance,
    RismSiglum,
    Segment,
    Sequence,
    Source
)
from main_app.forms import ContactForm
from django.core.mail import send_mail, get_connection
from django.contrib.auth.decorators import login_required, user_passes_test
from next_chants import next_chants
from django.contrib import messages
import random
from django.http import Http404
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied

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


def ajax_melody_list(request, cantus_id):
    """
    Function-based view responding to the AJAX call for melody list on the chant detail page,
    accessed with ``chants/<int:pk>``, click on "Display melodies connected with this chant"

    Args:
        cantus_id (str): The Cantus ID of the requested concordances group

    Returns:
        JsonResponse: A response to the AJAX call, to be unpacked by the frontend js code
    """
    chants = (
        Chant.objects.filter(cantus_id=cantus_id).exclude(volpiano=None).order_by("id")
    )

    display_unpublished = request.user.is_authenticated
    if not display_unpublished:
        chants = chants.filter(source__published=True)
    
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
        # OldCantus seems to use whichever is present: ms spelling, std spelling, incipit (in that order)
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
    try:
        source = Source.objects.get(id=source_id)
    except:
        raise Http404("This source does not exist")

    if not source.published:
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
            "differentia_new",
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
                entry.differentia_new,
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
    # submitted = False
    if request.method == "GET":
        skill_testing_questions = (
            "_antusdatabase",
            "c_ntusdatabase",
            "ca_tusdatabase",
            "can_usdatabase",
            "cant_sdatabase",
            "cantu_database",
            "cantus_atabase",
            "cantusd_tabase",
            "cantusda_abase",
            "cantusdat_base",
            "cantusdata_ase",
            "cantusdatab_se",
            "cantusdataba_e",
            "cantusdatabas_",
        )
        skill_testing_question = random.choice(skill_testing_questions)
        form = ContactForm()
        return render(request, "contact_form.html", {"form": form,
                "skill_testing_question": skill_testing_question,
            }
        )
    elif request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            st_question = request.POST.get("hidden_skill_testing_question")
            name = form.cleaned_data["name"]
            sender_email = form.cleaned_data["sender_email"]
            subject = form.cleaned_data["subject"]
            message = form.cleaned_data["message"]
            send_yourself_email = form.cleaned_data["send_yourself_email"]
            skill_test_response = form.cleaned_data["skill_testing_response"]
            # when changing recipients into a real email address, write it as an env variable
            recipients = ["info@test.com"]

            connection = get_connection(
                "django.core.mail.backends.console.EmailBackend"
                # "django.core.mail.backends.smtp.EmailBackend"
            )
            if st_question.replace("_", skill_test_response) == "cantusdatabase":
                # to implement eventually:
                #   the "name" field is currently not used
                #   the send_yourself_copy field is currently not used
                send_mail(subject, message, sender_email, recipients, connection=connection)
                messages.success(request, "Email successfully sent!")
                return HttpResponseRedirect("/contact")
            else:
                messages.error(request, "Incorrect missing character provided.")
                return HttpResponseRedirect("/contact")


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
    CHANT_CNT = 7

    if any(char.isdigit() for char in search_term):
        # if the search term contains at least one digit, assume user is searching by Cantus ID
        chants = Chant.objects.filter(cantus_id__istartswith=search_term).order_by(
            "id"
        )
    else:
        # if the search term does not contain any digits, assume user is searching by incipit
        chants = Chant.objects.filter(incipit__icontains=search_term).order_by("id")

    display_unpublished = request.user.is_authenticated
    if not display_unpublished:
        chants = chants.filter(source__published=True)
    
    chants = chants[:CHANT_CNT]

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


def json_melody_export(request, cantus_id):
    chants = Chant.objects.filter(cantus_id=cantus_id, volpiano__isnull=False, source__published=True)

    db_keys = ["melody_id",
        "id",
        "cantus_id",
        "siglum",
        "source__id", # don't fetch the entire Source object, just the id of
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

    chants_values = list(chants.values(*db_keys)) # a list of dictionaries. Each
                                                  # dictionary represents metadata on one chant

    def standardize_for_api(chant_values):
        keymap = { # map attribute names from Chant model (i.e. db_keys
            # in list above) to corresponding attribute names
            # in old API, and remove artifacts of query process (i.e. __id suffixes)
        "melody_id": "mid",                 # <-
        "id": "nid",                        # <-
        "cantus_id": "cid",                 # <-
        "siglum": "siglum",
        "source__id": "srcnid",             # <-
        "folio": "folio",
        "incipit": "incipit",
        "manuscript_full_text": "fulltext", # <-
        "volpiano": "volpiano",
        "mode": "mode",
        "feast__id": "feast",               # <-
        "office__id": "office",             # <-
        "genre__id": "genre",               # <-
        "position": "position",
        }
        
        standardized_chant_values = {keymap[key]: chant_values[key] for key in chant_values}

        # manually build a couple of last fields that aren't represented in Chant object
        chant_uri = request.build_absolute_uri(reverse("chant-detail", args=[chant_values["id"]]))
        standardized_chant_values["chantlink"] = chant_uri
        src_uri = request.build_absolute_uri(reverse("source-detail", args=[chant_values["source__id"]]))
        standardized_chant_values["srclink"] = src_uri

        return standardized_chant_values

    standardized_chants_values = [standardize_for_api(cv) for cv in chants_values]
    
    return JsonResponse(standardized_chants_values, safe=False)


def json_node_export(request, id):
    """
    returns all fields of the chant/sequence/source/indexer with the specified `id`
    """
    
    # future possible optimization: use .get() instead of .filter()
    chant = Chant.objects.filter(id=id)
    sequence = Sequence.objects.filter(id=id)
    source = Source.objects.filter(id=id)
    indexer = Indexer.objects.filter(id=id)

    if chant:
        if not chant.first().source.published:
            return HttpResponseNotFound()
        requested_item = chant
    elif sequence:
        if not sequence.first().source.published:
            return HttpResponseNotFound()
        requested_item = sequence
    elif source:
        if not source.first().published:
            return HttpResponseNotFound()
        requested_item = source
    elif indexer:
        requested_item = indexer
    else:
        # id does not correspond to a chant, sequence, source or indexer
        return HttpResponseNotFound()

    vals = dict(*requested_item.values())

    return JsonResponse(vals)


def json_sources_export(request):
    """
    generates a json object of published sources with their IDs and CSV links
    """
    sources = Source.objects.filter(published=True)
    ids = [source.id for source in sources]

    def inner_dictionary(id):
        # in OldCantus, json-sources creates a json file with each id attribute pointing to a dictionary
        # containing a single key, "csv", which itself points to a link to the relevant csv file.
        # inner_dictionary() is used to build this single-keyed dictionary.
        
        # To avoid confusion, note that the `id` parameter refers to an identifier, and is not
        # an abbreviation of `inner_dictionary`!
        return {"csv": request.build_absolute_uri(reverse("csv-export", args=[id]))}
    
    csv_links = {id: inner_dictionary(id) for id in ids}

    return JsonResponse(csv_links)


def json_nextchants(request, cantus_id):
    ids_and_counts = next_chants(cantus_id, display_unpublished=False)
    suggested_chants_dict = {id: count for (id, count) in ids_and_counts}
    return JsonResponse(suggested_chants_dict)
    

def handle404(request, exception):
    return render(request, "404.html")

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            # if the user is trying to change their password for the first time (the password that was given to them),
            # update the user's changed_initial_password boolean field to True
            if request.user.changed_initial_password == False:
                form.user.changed_initial_password = True
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
    else:
        form = PasswordChangeForm(request.user)
        if request.user.changed_initial_password == False:
            messages.warning(
                request,
                "The current password was assigned to you by default and is unsecure. Please make sure to change it for security purposes."
            )
    return render(request, 'registration/change_password.html', {
        'form': form
    })

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
        Century,
        Chant,
        Feast,
        Genre,
        Indexer,
        Notation,
        Office,
        Provenance,
        RismSiglum,
        Segment,
        Sequence,
        Source
    ]

    # get the 50 most recently updated objects for all of the models
    for model in models:
        for object in model.objects.all().order_by("-date_updated")[:50]:
            objects.append(object)

    objects.sort(key=lambda x: x.date_updated, reverse=True)
    recently_updated_50_objects = objects[:50]

    return render(request, "content_overview.html", {
        "objects": recently_updated_50_objects
    })
