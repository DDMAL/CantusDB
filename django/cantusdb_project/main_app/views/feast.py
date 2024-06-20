from collections import namedtuple
from typing import Generator, NamedTuple

from django.db import connection
from django.db.models.functions import Lower
from django.views.generic import DetailView, ListView
from extra_views import SearchableListMixin

from main_app.models import Feast

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
WHERE fs.id = %s AND cs.cantus_id IS NOT NULL {published_filt}
GROUP BY cs.cantus_id
ORDER BY ccount desc;"""

# This SQL query will return five columns: the source ID, shelfmark, the holding
# institution siglum and name, and count of the number of chants in that source
# that match a given feast.
feast_source_query: str = """SELECT DISTINCT ss.id AS source_id, ss.shelfmark, 
                COALESCE(hs.siglum, 'Private') as siglum, 
                hs.name AS institution_name, 
                (SELECT COUNT(cs2.id) 
                 FROM main_app_chant AS cs2 
                 WHERE cs2.source_id = ss.id AND cs2.feast_id = %s) AS chant_count
FROM main_app_source ss
         LEFT JOIN main_app_institution AS hs ON ss.holding_institution_id = hs.id
         LEFT JOIN main_app_chant AS cs ON cs.source_id = ss.id
         LEFT JOIN main_app_feast AS fs ON cs.feast_id = fs.id
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


class FeastDetailView(DetailView):
    model = Feast
    context_object_name = "feast"
    template_name = "feast_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        feast_id = self.object.pk

        display_unpublished = self.request.user.is_authenticated

        # if the user is not authenticated, restrict the chant count to
        # only those from published sources.
        if not display_unpublished:
            chant_sql_query = feast_chant_query.format(published_filt="AND ss.published IS TRUE")
            source_sql_query = feast_source_query.format(published_filt="AND ss.published IS TRUE")
        else:
            chant_sql_query = feast_chant_query.format(published_filt="")
            source_sql_query = feast_source_query.format(published_filt="")

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
