from django.views.generic import DetailView, ListView
from django.db.models.functions import Lower
from main_app.models import Feast, Source
from extra_views import SearchableListMixin

# this categorization is not finalized yet
# the feastcode on old cantus requires cleaning
# for now we just leave this categorization as it is
TEMP_PREFIX = [
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "16",
    "17",
]
SANC_PREFIX = ["12", "13", "14", "15"]


class FeastDetailView(DetailView):
    model = Feast
    context_object_name = "feast"
    template_name = "feast_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        display_unpublished = self.request.user.is_authenticated

        chants_in_feast = self.get_object().chant_set
        if not display_unpublished:
            chants_in_feast = chants_in_feast.filter(source__published=True)

        cantus_ids = list(
            chants_in_feast.values_list("cantus_id", flat=True).distinct()
        )

        counts = []
        incipits = []
        genres = []

        for cantus_id in cantus_ids:
            chants = chants_in_feast.filter(cantus_id=cantus_id)
            count = chants.count()
            incipit = chants.first().incipit
            genre = chants.first().genre

            counts.append(count)
            incipits.append(incipit)
            genres.append(genre)

        zipped = zip(cantus_ids, incipits, genres, counts)
        zipped = sorted(zipped, key=lambda t: t[3], reverse=True)
        context["frequent_chants_zip"] = zipped

        source_ids = list(
            chants_in_feast.values_list("source__id", flat=True).distinct()
        )
        sources = Source.objects.filter(id__in=source_ids)
        counts = [chants_in_feast.filter(source=source).count() for source in sources]

        zipped = zip(sources, counts)
        zipped = sorted(zipped, key=lambda t: t[1], reverse=True)
        context["sources_zip"] = zipped

        return context


class FeastListView(SearchableListMixin, ListView):
    """Searchable List view for Feast model

    Accessed by /feasts/

    When passed a ``?q=<query>`` argument in the GET request, it will filter feasts
    based on the fields defined in ``search_fields`` with the ``icontains`` lookup

    The feasts can also be filtered by `date` (temp/sanc) and `month` and ordered by `sort_by`,
    which are also passed as GET parameters
    """

    model = Feast
    search_fields = ["name", "description", "feast_code"]
    paginate_by = 100
    context_object_name = "feasts"
    template_name = "feast_list.html"

    def get_ordering(self) -> tuple:
        ordering = self.request.GET.get("sort_by")
        # feasts can be ordered by name or feast_code,
        # default to ordering by name if given anything else
        if ordering not in ["name", "feast_code"]:
            ordering = "name"
        # case insensitive ordering by name
        return (Lower(ordering),) if ordering == "name" else (ordering,)

    def get_queryset(self):
        queryset = super().get_queryset()
        date = self.request.GET.get("date")
        month = self.request.GET.get("month")
        # temp vs sanc categorization is not finalized yet,
        # the feastcode needs to be updated by the cantus people
        if date == "temp":
            queryset = queryset.filter(prefix__in=TEMP_PREFIX)
        elif date == "sanc":
            queryset = queryset.filter(prefix__in=SANC_PREFIX)

        if month and (int(month)) in range(1, 13):
            month = int(month)
            queryset = queryset.filter(month=month)

        return queryset
