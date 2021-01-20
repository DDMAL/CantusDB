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
    model = Chant
    queryset = Chant.objects.all().order_by("id")
    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["genres"] = Genre.objects.all().order_by("name").values("id", "name")
        return context

    def get_queryset(self):
        queryset = super().get_queryset()
        q_obj_filter = Q()
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
        if self.request.GET.get("incipit"):
            # Make list of terms split on spaces
            incipit_terms = self.request.GET.get("incipit").split(" ")
            incipit_q = Q()
            # For each term, add it to the Q object of each field with an OR operation.
            # We split the terms so that the words can be separated in the actual
            # field, allowing for a more flexible search, and a field needs
            # to match only one of the terms
            for term in incipit_terms:
                incipit_q |= Q(incipt__icontains=term)
            q_obj_filter &= incipit_q
        return queryset.filter(q_obj_filter)


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
