import csv
from django.http.response import JsonResponse
from django.http import HttpResponse
from django.shortcuts import render
from django.urls.base import reverse
from main_app.models import Chant, Sequence, Source, Feast, Genre, Indexer, Office


def items_count(request):
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
        "feast__name",
        "mode",
        "image_link",
    )

    concordances = list(concordance_values)
    for i, concordance in enumerate(concordances):
        concordance["source_link"] = chants[i].source.get_absolute_url()
        if chants[i].search_vector:
            concordance["chant_link"] = chants[i].get_absolute_url()
        else:
            concordance["chant_link"] = reverse("sequence-detail", args=[chants[i].id])
        concordance["db"] = "CD"

    concordance_count = len(concordances)
    return JsonResponse(
        {"concordances": concordances, "concordance_count": concordance_count},
        safe=False,
    )


def ajax_melody_list(request, cantus_id):
    chants = (
        Chant.objects.filter(cantus_id=cantus_id)
        .exclude(volpiano=None)
        .order_by("siglum", "folio")
    )

    # queryset(list of dictionaries)
    concordance_values = chants.values(
        "siglum",
        "folio",
        "office__name",
        "genre__name",
        "position",
        "feast__name",
        "volpiano",
        "mode",
        # seems to use whichever is present: ms spelling, std spelling, incipit
        "manuscript_full_text_std_spelling",
    )

    concordances = list(concordance_values)
    for i, concordance in enumerate(concordances):
        concordance["source_link"] = chants[i].source.get_absolute_url()
        concordance["ci_link"] = chants[i].get_ci_url()
        concordance["chant_link"] = chants[i].get_absolute_url()
        concordance["db"] = "CD"

    concordance_count = len(concordances)
    return JsonResponse(
        {"concordances": concordances, "concordance_count": concordance_count},
        safe=False,
    )


def csv_export(request, source_id):
    source = Source.objects.get(id=source_id)
    if source.segment.id == 4064:
        entries = source.sequence_set.order_by("id")
    else:
        entries = source.chant_set.order_by("id")

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
