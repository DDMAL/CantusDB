from django.views.generic import (
    DetailView,
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
)
from django.views import View
from django.db.models import Q
from main_app.models import Chant, Genre, Feast, Office, Source
from main_app.forms import ChantCreateForm
from django.shortcuts import get_object_or_404, HttpResponse

import requests
import lxml.html as lh

class ChantDetailView(DetailView):
    model = Chant
    context_object_name = "chant"
    template_name = "chant_detail.html"


class ChantListView(ListView):
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
    model = Chant
    template_name = "input_form_w.html"

    #fields = "__all__" # include all fields to the form
    # exclude = ['json_info'] # example of excluding sth from the form
    form_class = ChantCreateForm
    success_url = "/chants"

    def dispatch(self, request, *args, **kwargs):
        """
        Overridden so we can make sure the 'Source' specified in url exists
        before we display the form
        """
        self.source = get_object_or_404(Source, pk=kwargs['source_pk'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        form.instance.source = self.source # the same as the next line
        # form.instance.source = get_object_or_404(Source, pk=self.kwargs['source_pk'])

        # compute incipt, within 30 charactors, keep words complete
        words = form.instance.manuscript_full_text_std_spelling.split(" ")
        incipt = ""
        for word in words:
            new_incipt = incipt + word + ' '
            if len(new_incipt) >= 30:
                break
            else:
                incipt = new_incipt
        form.instance.incipt = incipt.strip(' ')
        return super().form_valid(form)

class ChantUpdateView(UpdateView):
    model = Chant
    template_name = "chant_form.html"
    fields = "__all__"
    success_url = "/chants"

class ChantCiSearchView(View):
    '''
    open a new window (done in js)
    get the search_term from the url
    do the search in python and write results in get_context_data
    render the table template
    '''
    def get(self, request, *args, **kwargs):
        # print(kwargs['search_term'])
        search_term = kwargs['search_term']
        url = "http://cantusindex.org/search?t="+search_term+"&cid=&genre=All&ghisp=All"

        page = requests.get(url)
        doc = lh.fromstring(page.content)

        #Parse data that are stored between <tr>..</tr> of HTML
        tr_elements = doc.xpath('//tr')

        #Create empty list
        cantus_id = []
        genre = []
        full_text = []

        # remove the table header
        tr_elements = tr_elements[1:]

        for row in tr_elements:
            cantus_id.append(row[0].text_content().strip())
            genre.append(row[1].text_content().strip())
            full_text.append(row[2].text_content().strip())
        # return HttpResponse(kwargs['search_term'])

class CISearchView(TemplateView):
    '''
    open a new window (done in js)
    get the search_term from the url
    do the search in python and write results in get_context_data
    render the table template
    '''
    
    template_name = "ci_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print(kwargs['search_term'])
        search_term = kwargs['search_term']

        p = {'t': search_term, 'cid': '', 'genre': 'All', 'ghisp': 'All'}
        r = requests.get('http://cantusindex.org/search', params=p)

        print(r.url)

        page = requests.get(r.url)
        doc = lh.fromstring(page.content)

        #Parse data that are stored between <tr>..</tr> of HTML
        tr_elements = doc.xpath('//tr')

        #Create empty list
        cantus_id = []
        genre = []
        full_text = []

        # remove the table header
        tr_elements = tr_elements[1:]

        for row in tr_elements:
            cantus_id.append(row[0].text_content().strip())
            genre.append(row[1].text_content().strip())
            full_text.append(row[2].text_content().strip())

        # context['cantus_ids'] = cantus_id
        # context['genres'] = genre
        # context['full_texts'] = full_text

        # for looping through three lists in template, we have to zip it here
        if len(cantus_id)==0:
            context['results'] = [['No results', 'No results', 'No results']]
        else:
            context['results'] = zip(cantus_id, genre, full_text)

        context['num'] = [1,2,3]
        return context