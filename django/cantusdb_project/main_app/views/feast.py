from collections import namedtuple
from typing import Generator, NamedTuple, Any, Dict, Tuple

from django.db import connection
from django.db.models import QuerySet
from django.db.models.functions import Lower
from django.views.generic import DetailView, ListView
from extra_views import SearchableListMixin

from main_app.models import Feast
from main_app.permissions import CustomAccessMixin

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


# This SQL Query will return four columns: cantus_id, ccount, incipit, and genres.
# These will be the field names when turned in to the Result named tuple. The genre
# column is an aggregate array of genre entries, with the separator "::" between the
# fields.
feast_chant_query: str = """SELECT cs.cantus_id, COUNT(cs.cantus_id) AS ccount,
       (SELECT cs2.incipit
        FROM main_app_chant AS cs2
        WHERE cs.cantus_id = cs2.cantus_id
        ORDER BY cs2.id LIMIT 1) as incipit,
        array_remove(
               array_agg(DISTINCT gs.id || '::' || gs.name || '::' || gs.description),
               NULL
       ) AS genres
FROM main_app_feast AS fs
LEFT JOIN main_app_chant AS cs ON cs.feast_id = fs.id
LEFT JOIN main_app_source AS ss ON cs.source_id = ss.id
LEFT JOIN main_app_genre AS gs ON cs.genre_id = gs.id
LEFT JOIN main_app_source_current_editors AS sce ON ss.id = sce.source_id
WHERE fs.id = %s AND cs.cantus_id IS NOT NULL {published_filt}
GROUP BY cs.cantus_id
ORDER BY ccount desc;"""

# This SQL query will return five columns: the source ID, shelfmark, the holding
# institution siglum and name, and count of the number of chants in that source
# that match a given feast.
# The siglum expression reimplements the institution-siglum fallback of
# `Source.compose_short_heading` in SQL: a missing, empty, or placeholder
# ("XX-NN") institution siglum displays as "Cantus". The shelfmark is appended
# to it in the template (feast_detail.html). Keep the two in sync.
feast_source_query: str = """SELECT DISTINCT ss.id AS source_id, ss.shelfmark,
                COALESCE(NULLIF(NULLIF(hs.siglum, ''), 'XX-NN'), 'Cantus') as siglum,
                hs.name AS institution_name, 
                (SELECT COUNT(cs2.id) 
                 FROM main_app_chant AS cs2 
                 WHERE cs2.source_id = ss.id AND cs2.feast_id = %s) AS chant_count
FROM main_app_source ss
         LEFT JOIN main_app_institution AS hs ON ss.holding_institution_id = hs.id
         LEFT JOIN main_app_chant AS cs ON cs.source_id = ss.id
         LEFT JOIN main_app_feast AS fs ON cs.feast_id = fs.id
         LEFT JOIN main_app_source_current_editors AS sce ON ss.id = sce.source_id
WHERE fs.id = %s AND cs.cantus_id IS NOT NULL {published_filt}
GROUP BY ss.id, hs.name, hs.siglum
ORDER BY chant_count DESC, siglum;
"""


def namedtuple_fetch(results, description) -> Generator[NamedTuple, None, None]:
    """
    Yields a generator of a result as a named tuple.

    This is mostly taken from the Django documentation, but instead of iterating over the full
    result set and returning a new list, this yields the Result object for every iteration
    as it's used in the template.

    :param results: A list of results from the database.
    :param description: A description of the columns used for naming the fields in the tuple.
    :return: A generator that wraps a result row in a Result named tuple.
    """
    nt_result = namedtuple("Result", [col[0] for col in description])
    for res in results:
        yield nt_result(*res)


class FeastDetailView(CustomAccessMixin, DetailView):  # type: ignore[type-arg]
    model = Feast
    context_object_name = "feast"
    template_name = "feast_detail.html"
    test_req = False

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        feast_id = self.object.pk

        # We use some methods from the CustomAccessMixin to write the
        # source filter portion of the above SQL queries.
        if not self.user.is_authenticated:
            src_filter_q = "AND ss.published IS TRUE"
        elif self.user.is_superuser or self.user_is_global_viewer:
            src_filter_q = ""
        else:
            src_filter_q = f"AND (ss.published IS TRUE OR sce.user_id = {self.user.id})"

        chant_sql_query = feast_chant_query.format(published_filt=src_filter_q)
        source_sql_query = feast_source_query.format(published_filt=src_filter_q)

        with connection.cursor() as cursor:
            cursor.execute(chant_sql_query, [feast_id])
            num_chant_results = cursor.rowcount
            chants_from_db = namedtuple_fetch(cursor.fetchall(), cursor.description)

        context["frequent_chants"] = chants_from_db
        context["frequent_chants_count"] = num_chant_results

        with connection.cursor() as cursor:
            cursor.execute(source_sql_query, [feast_id, feast_id])
            num_sources_results = cursor.rowcount
            sources_from_db = namedtuple_fetch(cursor.fetchall(), cursor.description)

        context["sources"] = sources_from_db
        context["sources_count"] = num_sources_results

        return context


class FeastListView(SearchableListMixin, ListView):  # type: ignore[type-arg]
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

    def get_ordering(self) -> Tuple[str]:
        ordering = self.request.GET.get("sort_by")
        # feasts can be ordered by name or feast_code,
        # default to ordering by name if given anything else
        if ordering not in ["name", "feast_code"]:
            ordering = "name"
        # case insensitive ordering by name
        return (Lower(ordering),) if ordering == "name" else (ordering,)

    def get_queryset(self) -> QuerySet[Feast]:
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
