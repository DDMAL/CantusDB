from django.views.generic import (
    DetailView,
    ListView,
    CreateView,
    UpdateView,
)
from django.db.models import Q, F, QuerySet
from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
)
from main_app.models import Chant, Genre, Feast
from main_app.forms import ChantCreateForm


class ChantDetailView(DetailView):
    """
    Displays a single Chant object. Accessed with ``chants/<int:pk>``
    """

    model = Chant
    context_object_name = "chant"
    template_name = "chant_detail.html"


class ChantListView(ListView):
    """
    Displays a list of Chant objects. Accessed with ``chants/``
    """

    model = Chant
    queryset = Chant.objects.all().order_by("id")
    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_list.html"


class ChantSearchView(ListView):
    """
    Searches Chants and displays them as a list, accessed with ``chant-search/``

    If no ``GET`` parameters, returns all chants

    ``GET`` parameters:
        ``genre``: Filters by Genre of Chant
        ``cantus_id``: Filters by the Cantus ID field of Chant
        ``mode``: Filters by mode of Chant
        ``melodies``: Filters Chant by whether or not it contains a melody in
                      Volpiano form. Valid values are "true" or "false".
        ``feast``: Filters by Feast of Chant
        ``incipit``: Searches text of Chant for keywords
    """

    model = Chant
    queryset = Chant.objects.all().order_by("id")
    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_search.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        # Add to context a QuerySet of dicts with id and name of each Genre
        context["genres"] = (
            Genre.objects.all().order_by("name").values("id", "name")
        )
        return context

    def get_queryset(self) -> QuerySet:
        queryset = super().get_queryset()
        # Create a Q object to filter the QuerySet of Chants
        q_obj_filter = Q()

        # For every GET parameter other than incipit, add to the Q object
        if self.request.GET.get("genre"):
            genre_id = int(self.request.GET.get("genre"))
            q_obj_filter &= Q(genre__id=genre_id)
        if self.request.GET.get("cantus_id"):
            cantus_id = self.request.GET.get("cantus_id")
            q_obj_filter &= Q(cantus_id=cantus_id)
        if self.request.GET.get("mode"):
            mode = self.request.GET.get("mode")
            q_obj_filter &= Q(mode=mode)
        if self.request.GET.get("melodies") in ["true", "false"]:
            melodies = self.request.GET.get("melodies")
            if melodies == "true":
                q_obj_filter &= Q(volpiano__isnull=False)
            if melodies == "false":
                q_obj_filter &= Q(volpiano__isnull=True)
        if self.request.GET.get("feast"):
            feast = self.request.GET.get("feast")
            feast = Feast.objects.filter(name=feast)
            q_obj_filter &= Q(feast=feast)

        # Filter the QuerySet with Q object
        queryset = queryset.filter(q_obj_filter)

        # TODO: change incipit to "keyword" maybe? More clear since it is
        # searching the whole text

        # Finally, use the incipit parameter to do keyword searching
        # over the QuerySet
        if self.request.GET.get("incipit"):
            incipt = self.request.GET.get("incipit")
            queryset = self.keyword_search(queryset, incipt)

        return queryset

    def keyword_search(self, queryset: QuerySet, keyword: str) -> QuerySet:
        """
        Performs a keyword search over a QuerySet of Chants

        Uses PostgreSQL's full text search features

        Args:
            queryset (QuerySet): A QuerySet of Chants to be searched
            keyword (str): A string of keywords to search the QuerySet

        Returns:
            QuerySet: A QuerySet of Chants filtered by keywords
        """
        query = SearchQuery(keyword)
        rank_annotation = SearchRank(F("search_vector"), query)
        filtered_queryset = (
            queryset.annotate(rank=rank_annotation)
            .filter(search_vector=query)
            .order_by("-rank")
        )
        return filtered_queryset


class ChantCreateView(CreateView):
    """
    Creates a single Chant. Accessed by ``chant-create/
    """

    # template_name = "chant_form.html"
    template_name = "input_form_w.html"

    # fields = "__all__" # include all fields to the form
    # exclude = ['json_info'] # example of excluding sth from the form
    form_class = ChantCreateForm
    success_url = "/chants"
    """
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["genres"] = Genre.objects.all().order_by("name").values("id", "name")
        context["offices"] = Office.objects.all().order_by("name").values("id", "name")
        context["feasts"] = Feast.objects.all().order_by("name").values("id", "name")
        return context
    """


class ChantUpdateView(UpdateView):
    """
    Updates a single Chant. Accessed by ``chant-update/<int:pk>``
    """

    model = Chant
    template_name = "chant_form.html"
    fields = "__all__"
    success_url = "/chants"
