from django.shortcuts import render
from main_app.models import Chant, Sequence, Source, Feast, Genre, Indexer, Office


def items_count(request):
    chant_count = Chant.objects.count()
    sequence_count = Sequence.objects.count()
    source_count = Source.objects.count()
    feast_count = Feast.objects.count()
    genre_count = Genre.objects.count()
    indexer_count = Indexer.objects.count()
    office_count = Office.objects.count()

    context = {
        "chant_count": chant_count,
        "sequence_count": sequence_count,
        "source_count": source_count,
        "feast_count": feast_count,
        "genre_count": genre_count,
        "indexer_count": indexer_count,
        "office_count": office_count,
    }
    return render(request, "items_count.html", context)

