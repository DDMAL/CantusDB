from django.views.generic import (
    DetailView,
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
)
from django.db.models import Q
from main_app.models import Chant, Genre, Feast, Office, Source
from main_app.forms import ChantCreateForm
from django.shortcuts import get_object_or_404, HttpResponse

import requests
import lxml.html as lh
from django.urls import reverse, reverse_lazy


class ChantDetailView(DetailView):
    model = Chant
    context_object_name = "chant"
    template_name = "chant_detail.html"


class ChantListView(ListView):
    model = Chant
    queryset = Chant.objects.all().order_by("id")
    paginate_by = 18
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
    model = Chant
    template_name = "input_form_w.html"
    form_class = ChantCreateForm
    # if success_url and get_success_url not specified, will direct to chant detail page
    def get_success_url(self):
        return reverse("chant-create", args=[self.source.id])

    def get_initial(self):
        self.latest_folio, self.latest_feast = self.get_folio_and_feast()
        return {
            "folio": self.latest_folio,
            "feast": self.latest_feast,
            "sequence_number": self.get_latest_sequence(),
        }

    def get_folio_and_feast(self):
        # get the default [folio, feast] from the last created chant
        # last created chant has the largest id, so order by id
        chants_in_source = (
            Chant.objects.all().filter(source=self.source).order_by("-id")
        )
        try:
            latest_chant = chants_in_source[0]
            latest_folio = latest_chant.folio
            latest_feast = latest_chant.feast.id
        except:
            # if the source do not have any chant yet
            latest_folio = "001r"
            latest_feast = ""
        return latest_folio, latest_feast

    def get_latest_sequence(self):
        # compute sequence number, automatically get the latest sequence number in the folio
        chants_in_folio = Chant.objects.all().filter(
            source=self.source, folio=self.latest_folio
        )
        sequences_in_folio = chants_in_folio.values("sequence_number").order_by(
            "-sequence_number"
        )
        try:
            latest_sequence = sequences_in_folio[0]["sequence_number"]
        except:
            # there exist sources that do not have any chants yet, in this case, autofill 001r
            latest_sequence = 0
        print("latest_seq: ", latest_sequence)
        return int(latest_sequence) + 1

    def dispatch(self, request, *args, **kwargs):
        """
        Overridden so we can make sure the 'Source' specified in url exists
        before we display the form
        """
        self.source = get_object_or_404(Source, pk=kwargs["source_pk"])
        self.source_id = kwargs["source_pk"]
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source_link"] = reverse("source-detail", args=[self.source_id])
        context["source"] = self.source
        return context

    def form_valid(self, form):
        # compute source
        form.instance.source = self.source  # same effect as the next line
        # form.instance.source = get_object_or_404(Source, pk=self.kwargs['source_pk'])

        # compute incipt, within 30 charactors, keep words complete
        words = form.instance.manuscript_full_text_std_spelling.split(" ")
        incipt = ""
        for word in words:
            new_incipt = incipt + word + " "
            if len(new_incipt) >= 30:
                break
            incipt = new_incipt
        form.instance.incipt = incipt.strip(" ")

        # if the folio field is left empty
        if form.instance.folio == None:
            form.instance.folio = self.latest_folio

        # if the sequence field is left empty
        if form.instance.sequence_number == None:
            form.instance.sequence_number = self.get_latest_sequence()

        # if a chant with the same sequence and folio already exists in the source
        if (
            Chant.objects.all()
            .filter(
                source=self.source,
                folio=form.instance.folio,
                sequence_number=form.instance.sequence_number,
            )
            .exists()
        ):
            form.add_error(
                None,
                "Chant with the same sequence and folio already exists in the source. Please make sure you're in the right source and check your entry for 'Folio' and 'Sequence'",
            )

        if form.is_valid():
            return super().form_valid(form)
        else:
            return super().form_invalid(form)


class ChantDeleteView(DeleteView):
    model = Chant
    success_url = reverse_lazy("chant-list")
    template_name = "chant_confirm_delete.html"


class ChantUpdateView(UpdateView):
    model = Chant
    template_name = "chant_form.html"
    fields = "__all__"
    success_url = "/chants"


class CISearchView(TemplateView):
    """
    open a new window (done in js)
    get the search_term from the url
    do the search in python and write results in get_context_data
    render the table template
    """

    template_name = "ci_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search_term = kwargs["search_term"]
        search_term = search_term.replace(" ", "+")  # for multiple keywords
        # Create empty list for the 3 types of info
        cantus_id = []
        genre = []
        full_text = []

        # scrape multiple pages
        pages = range(0, 5)
        for page in pages:
            p = {
                "t": search_term,
                "cid": "",
                "genre": "All",
                "ghisp": "All",
                "page": page,
            }
            page = requests.get("http://cantusindex.org/search", params=p)
            doc = lh.fromstring(page.content)
            # Parse data that are stored between <tr>..</tr> of HTML
            tr_elements = doc.xpath("//tr")
            # if cantus index returns an empty table
            if not tr_elements:
                break

            # remove the table header
            tr_elements = tr_elements[1:]

            for row in tr_elements:
                cantus_id.append(row[0].text_content().strip())
                genre.append(row[1].text_content().strip())
                full_text.append(row[2].text_content().strip())

        # for looping through three lists in template, we have to zip it here
        if len(cantus_id) == 0:
            context["results"] = [["No results", "No results", "No results"]]
        else:
            context["results"] = zip(cantus_id, genre, full_text)
        return context
