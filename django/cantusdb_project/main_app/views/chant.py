import enum
from re import I
import lxml.html as lh
import requests
import urllib
import json
from django.contrib import messages
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F, Q, QuerySet, query
from django.shortcuts import get_object_or_404
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from main_app.forms import ChantCreateForm
from main_app.models import Chant, Feast, Genre, Source, Sequence
from latin_syllabification import syllabify_text, syllabify_word
from syllabification_re import *


def keyword_search(queryset: QuerySet, keywords: str) -> QuerySet:
    """
    Performs a keyword search over a QuerySet

    Uses PostgreSQL's full text search features

    Args:
        queryset (QuerySet): A QuerySet to be searched
        keywords (str): A string of keywords to search the QuerySet

    Returns:
        QuerySet: A QuerySet filtered by keywords
    """
    query = SearchQuery(keywords)
    rank_annotation = SearchRank(F("search_vector"), query)
    filtered_queryset = (
        queryset.annotate(rank=rank_annotation)
        .filter(search_vector=query)
        .order_by("-rank")
    )
    return filtered_queryset


class ChantDetailView(DetailView):
    """
    Displays a single Chant object. Accessed with ``chants/<int:pk>``
    """

    model = Chant
    context_object_name = "chant"
    template_name = "chant_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chant = self.get_object()

        chants_in_source = chant.source.chant_set
        context["folios"] = (
            chants_in_source.values_list("folio", flat=True)
            .distinct()
            .order_by("folio")
        )
        folio_list = list(context["folios"])
        index = folio_list.index(chant.folio)
        context["previous_folio"] = folio_list[index - 1] if index != 0 else None
        context["next_folio"] = (
            folio_list[index + 1] if index < len(folio_list) - 1 else None
        )

        chants_current_folio = chants_in_source.filter(
            folio=chant.folio
        ).prefetch_related("feast")

        def get_chants_with_feasts(chants_in_folio):
            feast_ids = []
            for chant in chants_in_folio.order_by("sequence_number"):
                if chant.feast:
                    feast_ids.append(chant.feast.id)
            # remove duplicate feast ids and preserve the order
            feast_ids = list(dict.fromkeys(feast_ids))

            feasts = []
            for feast_id in feast_ids:
                feasts.append(Feast.objects.get(id=feast_id))
            # feasts = Feast.objects.filter(id__in=feast_ids) # this loses the order
            chants_in_feast = []
            for feast in feasts:
                chants = chants_in_folio.filter(feast=feast).order_by("sequence_number")
                chants_in_feast.append(chants)
            feasts_zip = zip(feasts, chants_in_feast)
            return feasts_zip

        context["feasts_current_folio"] = list(
            get_chants_with_feasts(chants_current_folio)
        )

        if context["previous_folio"]:
            chants_previous_folio = chants_in_source.filter(
                folio=context["previous_folio"]
            ).prefetch_related("feast")
            context["feasts_previous_folio"] = list(
                get_chants_with_feasts(chants_previous_folio)
            )

        if context["next_folio"]:
            chants_next_folio = chants_in_source.filter(
                folio=context["next_folio"]
            ).prefetch_related("feast")
            context["feasts_next_folio"] = list(
                get_chants_with_feasts(chants_next_folio)
            )

        # syllabification section
        if chant.volpiano:
            syls_melody = syllabize_melody(chant.volpiano)
            # print(syls_melody)

            if chant.manuscript_syllabized_full_text:
                syls_text = syllabize_text(
                    chant.manuscript_syllabized_full_text, pre_syllabized=True
                )

            elif chant.manuscript_full_text:
                syls_text = syllabize_text(
                    chant.manuscript_full_text, pre_syllabized=False
                )

            else:
                syls_text = syllabize_text(chant.incipit, pre_syllabized=False)
            # print(syls_text)
            syls_text, syls_melody = postprocess(syls_text, syls_melody)
            # print(syls_text)
            word_zip = align(syls_text, syls_melody)
            # rectified_melody = postprocess_symbols(syls_text, syls_melody, tilda_found)
            # text_melody_zip = align_melody_with_text(syls_text, rectified_melody)

            context["syllabized_text_with_melody"] = word_zip
        return context


class ChantListView(ListView):
    """
    Displays a list of Chant objects. Accessed with ``chants/`` followed by a series of GET params
    """

    model = Chant
    queryset = (
        Chant.objects.all()
        .filter(source__visible=True, source__public=True)
        .order_by("id")
    )
    paginate_by = 50
    context_object_name = "chants"
    template_name = "chant_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        source_id = self.request.GET.get("source")
        feast_id = self.request.GET.get("feast")
        genre_id = self.request.GET.get("genre")
        folio = self.request.GET.get("folio")
        search_text = self.request.GET.get("search_text")

        if source_id:
            queryset = queryset.filter(source__id=source_id)
        if feast_id:
            queryset = queryset.filter(feast__id=feast_id)
        if genre_id:
            queryset = queryset.filter(genre__id=genre_id)
        if folio:
            queryset = queryset.filter(folio=folio)
        if search_text:
            search_text = search_text.replace("+", " ").strip(" ")
            queryset = queryset.filter(
                Q(manuscript_full_text_std_spelling__icontains=search_text)
                | Q(incipit__icontains=search_text)
                | Q(manuscript_full_text__icontains=search_text)
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # these are needed in the left part selectors, unrelated to stuff on the right
        context["sources"] = Source.objects.all().order_by("siglum")
        context["feasts"] = Feast.objects.all().order_by("name")
        context["genres"] = Genre.objects.all().order_by("name")

        source_id = self.request.GET.get("source")
        source = Source.objects.get(id=source_id)
        context["source"] = source
        chants_in_source = source.chant_set
        if chants_in_source.count() == 0:
            context["folios"] = None
            context["feasts_with_folios"] = None
            context["previous_folio"] = None
            context["next_folio"] = None
            return context

        folios = (
            chants_in_source.values_list("folio", flat=True)
            .distinct()
            .order_by("folio")
        )
        context["folios"] = folios

        if self.request.GET.get("folio"):
            folio = self.request.GET.get("folio")
            index = list(folios).index(folio)
            context["previous_folio"] = folios[index - 1] if index != 0 else None
            context["next_folio"] = (
                folios[index + 1] if index < len(folios) - 1 else None
            )

        # for the feast selector on the right,
        # feasts are aligned with the corresponding folios
        folios_with_feasts = []
        feasts_with_folios = []

        folios_with_feasts.append(folios[0])
        current_feast = (
            chants_in_source.filter(folio=folios[0])
            .exclude(feast=None)
            .order_by("sequence_number")
            .first()
            .feast
        )
        feasts_with_folios.append(current_feast)

        for folio in folios:
            chants_on_folio = chants_in_source.filter(folio=folio).order_by(
                "sequence_number"
            )
            for chant in chants_on_folio:
                if chant.feast != current_feast:
                    feasts_with_folios.append(chant.feast)
                    folios_with_feasts.append(folio)
                    current_feast = chant.feast

        feast_zip = zip(folios_with_feasts, feasts_with_folios)
        # the options for the feast selector on the right
        context["feasts_with_folios"] = feast_zip
        return context


class ChantByCantusIDView(ListView):
    # model = Chant
    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_seq_by_cantus_id.html"

    def dispatch(self, request, *args, **kwargs):
        # decode cantus_id, which might contain forward slash and is thus percent-encoded
        self.cantus_id = urllib.parse.unquote(kwargs["cantus_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        chant_set = Chant.objects.filter(cantus_id=self.cantus_id, visible_status=1)
        sequence_set = Sequence.objects.filter(
            cantus_id=self.cantus_id, visible_status=1
        )
        # the union operation turns sequences into chants, the resulting queryset contains only "chant" objects
        # this forces us to do something special on the template to render correct absolute url for sequences
        queryset = chant_set.union(sequence_set)
        queryset = queryset.order_by("siglum")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cantus_id"] = self.cantus_id
        return context


class ChantSearchView(ListView):
    """
    Searches Chants and displays them as a list, accessed with ``chant-search/``

    This view uses the same template as ``ChantSearchMSView``

    If no ``GET`` parameters, returns all chants

    ``GET`` parameters:
        ``office``: Filters by Office of Chant
        ``genre``: Filters by Genre of Chant
        ``cantus_id``: Filters by the Cantus ID field of Chant
        ``mode``: Filters by mode of Chant
        ``melodies``: Filters Chant by whether or not it contains a melody in
                      Volpiano form. Valid values are "true" or "false".
        ``feast``: Filters by Feast of Chant
        ``keyword``: Searches text of Chant for keywords
        ``op``: Operation to take with keyword search. Options are "contains" and "starts_with"
    """

    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_search.html"

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        # Add to context a QuerySet of dicts with id and name of each Genre
        context["genres"] = Genre.objects.all().order_by("name").values("id", "name")
        return context

    def get_queryset(self) -> QuerySet:
        # Create a Q object to filter the QuerySet of Chants
        q_obj_filter = Q()

        # if the search is accessed by the global search bar
        if self.request.GET.get("search_bar"):
            chant_set = Chant.objects.filter(source__public=True, source__visible=True)
            sequence_set = Sequence.objects.filter(
                source__public=True, source__visible=True
            )
            if self.request.GET.get("search_bar").replace(" ", "").isalpha():
                # if search bar is doing incipit search
                incipit = self.request.GET.get("search_bar")
                chant_set = keyword_search(chant_set, incipit)
                sequence_set = keyword_search(sequence_set, incipit)
                queryset = chant_set.union(sequence_set)
                # queryset = keyword_search(queryset, incipit)
            else:
                # if search bar is doing Cantus ID search
                cantus_id = self.request.GET.get("search_bar")
                q_obj_filter &= Q(cantus_id=cantus_id)
                chant_set = chant_set.filter(q_obj_filter)
                sequence_set = sequence_set.filter(q_obj_filter)
                queryset = chant_set.union(sequence_set)
                # queryset = queryset.filter(q_obj_filter)

        else:
            # "office" (or any other field) should be a key in the GET if the search button has been clicked,
            # even if the user put nothing into the search form and hits "apply" immediately.
            # In that case, we return the all chants + seqs filtered by the search form.
            # On the contrary, if the user just arrived at the search page, there should be no params in GET
            # In that case, we return an empty queryset.
            if not "office" in self.request.GET:
                return Chant.objects.none()
            # For every GET parameter other than incipit, add to the Q object
            if self.request.GET.get("office"):
                office = self.request.GET.get("office")
                q_obj_filter &= Q(office__name__icontains=office)
            if self.request.GET.get("genre"):
                genre_id = int(self.request.GET.get("genre"))
                q_obj_filter &= Q(genre__id=genre_id)
            if self.request.GET.get("cantus_id"):
                cantus_id = self.request.GET.get("cantus_id")
                q_obj_filter &= Q(cantus_id__icontains=cantus_id)
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
                # This will match any feast whose name contains the feast parameter
                # as a substring
                feasts = Feast.objects.filter(name__icontains=feast)
                q_obj_filter &= Q(feast__in=feasts)

            chant_set = Chant.objects.filter(source__public=True, source__visible=True)
            sequence_set = Sequence.objects.filter(
                source__public=True, source__visible=True
            )
            # Filter the QuerySet with Q object
            chant_set = chant_set.filter(q_obj_filter)
            sequence_set = sequence_set.filter(q_obj_filter)
            # Finally, do keyword searching over the querySet
            if self.request.GET.get("keyword"):
                keyword = self.request.GET.get("keyword")
                # the operation parameter can be "contains" or "starts_with"
                if self.request.GET.get("op") == "contains":
                    chant_set = keyword_search(chant_set, keyword)
                    sequence_set = keyword_search(sequence_set, keyword)
                else:
                    chant_set = chant_set.filter(incipit__istartswith=keyword)
                    sequence_set = sequence_set.filter(incipit__istartswith=keyword)

            # once unioned, the queryset cannot be filtered/annotated anymore, so we put union to the last
            queryset = chant_set.union(sequence_set)
            # ordering with the folio string gives wrong order
            # old cantus is also not strictly ordered by folio (there are outliers)
            # so we order by id for now, which is the order that the chants are entered into the DB
            queryset = queryset.order_by("siglum", "id")

        return queryset


class ChantSearchMSView(ListView):
    """
    Searches chants/seqs in a certain manuscript, accessed with ``chant-search/<int:source_pk>``

    This view uses the same template as ``ChantSearchView``

    If no ``GET`` parameters, returns all chants

    ``GET`` parameters:
        ``office``: Filters by the office/mass of Chant
        ``genre``: Filters by Genre of Chant
        ``cantus_id``: Filters by the Cantus ID field of Chant
        ``mode``: Filters by mode of Chant
        ``melodies``: Filters Chant by whether or not it contains a melody in
                      Volpiano form. Valid values are "true" or "false".
        ``feast``: Filters by Feast of Chant
        ``keyword``: Searches text of Chant for keywords
        ``op``: Operation to take with keyword search. Options are "contains" and "starts_with"
    """

    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add to context a QuerySet of dicts with id and name of each Genre
        context["genres"] = Genre.objects.all().order_by("name").values("id", "name")
        # This is searching in a specific source, pass the source into context
        source_id = self.kwargs["source_pk"]
        context["source"] = Source.objects.get(id=source_id)
        return context

    def get_queryset(self) -> QuerySet:
        # Create a Q object to filter the QuerySet of Chants
        q_obj_filter = Q()
        # If the "apply" button hasn't been clicked
        if not "office" in self.request.GET:
            return Chant.objects.none()
        # For every GET parameter other than incipit, add to the Q object
        if self.request.GET.get("office"):
            office = self.request.GET.get("office")
            q_obj_filter &= Q(office__name__icontains=office)
        if self.request.GET.get("genre"):
            genre_id = int(self.request.GET.get("genre"))
            q_obj_filter &= Q(genre__id=genre_id)
        if self.request.GET.get("cantus_id"):
            cantus_id = self.request.GET.get("cantus_id")
            q_obj_filter &= Q(cantus_id__icontains=cantus_id)
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
            # This will match any feast whose name contains the feast parameter
            # as a substring
            feasts = Feast.objects.filter(name__icontains=feast)
            q_obj_filter &= Q(feast__in=feasts)

        source_id = self.kwargs["source_pk"]
        source = Source.objects.get(id=source_id)

        queryset = (
            source.sequence_set if source.segment.id == 4064 else source.chant_set
        )
        queryset = queryset.filter(source__public=True, source__visible=True)

        # Filter the QuerySet with Q object
        queryset = queryset.filter(q_obj_filter)
        # Finally, do keyword searching over the QuerySet
        if self.request.GET.get("keyword"):
            keyword = self.request.GET.get("keyword")
            # the operation parameter can be "contains" or "starts_with"
            if self.request.GET.get("op") == "contains":
                queryset = keyword_search(queryset, keyword)
            else:
                queryset = queryset.filter(incipit__istartswith=keyword)
        # ordering with the folio string gives wrong order
        # old cantus is also not strictly ordered by folio (there are outliers)
        # so we order by id for now, which is the order that the chants are entered into the DB
        queryset = queryset.order_by("siglum", "id")
        return queryset


class ChantCreateView(CreateView):
    """Create chant at /chant-create/<source-id>"""

    model = Chant
    template_name = "input_form_w.html"
    form_class = ChantCreateForm
    # if success_url and get_success_url not specified, will direct to chant detail page
    def get_success_url(self):
        return reverse("chant-create", args=[self.source.id])

    def get_initial(self):
        (
            self.latest_folio,
            self.latest_feast,
            self.latest_seq,
            self.latest_image,
        ) = self.get_folio_feast_seq_image()
        return {
            "folio": self.latest_folio,
            "feast": self.latest_feast,
            "sequence_number": self.latest_seq,
            "image_link": self.latest_image,
        }

    def get_folio_feast_seq_image(self):
        """get the default [folio, feast, seq] from the last created chant
        last created chant is found using 'date-updated'
        """
        chants_in_source = (
            Chant.objects.all().filter(source=self.source).order_by("-date_updated")
        )
        if not chants_in_source:
            # if there is no chant in source
            latest_folio = "001r"
            latest_feast = ""
            latest_seq = 0
            latest_image = ""
        else:
            latest_chant = chants_in_source[0]
            if latest_chant.folio:
                latest_folio = latest_chant.folio
            else:
                latest_folio = "001r"
            if latest_chant.feast:
                latest_feast = latest_chant.feast.id
            else:
                latest_feast = ""
            if latest_chant.sequence_number:
                latest_seq = latest_chant.sequence_number
            else:
                latest_seq = 0
            if latest_chant.image_link:
                latest_image = latest_chant.image_link
            else:
                latest_image = ""
        return latest_folio, latest_feast, latest_seq + 1, latest_image

    def dispatch(self, request, *args, **kwargs):
        """Make sure the source specified in url exists before we display the form"""
        self.source = get_object_or_404(Source, pk=kwargs["source_pk"])
        self.source_id = kwargs["source_pk"]
        return super().dispatch(request, *args, **kwargs)

    def get_suggested_chants(self):
        """get suggested chants based on the previous chant entered
        look for the CantusID of the previous chant in any source,
        compile a list of all the chants (CantusIDs) that follow it (use seq) on the same or the next folio,
        using these CantusIDs, search in CI for the correct full-text/genre
        To search CantusID on CI, use json export: 'http://cantusindex.org/json-cid/<CantusID>'

        Returns:
            list of dicts: a list of suggested chants in key-value pairs
        """

        # only displays the chants that occur most often
        NUM_SUGGESTIONS = 5

        cantus_ids = []
        nocs = []  # number of occurence
        # only load the fields that we need, this helps speed things up
        chants_in_source = Chant.objects.filter(source=self.source).only(
            "date_updated", "cantus_id"
        )
        if not chants_in_source:
            return None
        latest_chant = chants_in_source.latest("date_updated")
        cantus_id = latest_chant.cantus_id
        if cantus_id is None:
            return None
        chants_same_cantus_id = Chant.objects.filter(cantus_id=cantus_id).only(
            "source", "folio", "sequence_number"
        )
        for chant in chants_same_cantus_id:
            next_chant = chant.get_next_chant()
            if next_chant:
                # return the number of occurence in the suggestions (not in the entire db)
                if not next_chant.cantus_id in cantus_ids:
                    # cantus_id can be None (some chants don't have one)
                    if next_chant.cantus_id:
                        # add the new cantus_id to the list, count starts from 1
                        cantus_ids.append(next_chant.cantus_id)
                        nocs.append(1)
                if next_chant.cantus_id in cantus_ids:
                    idx = cantus_ids.index(next_chant.cantus_id)
                    nocs[idx] = nocs[idx] + 1
        # sort the nocs and cantus_ids
        sorted_list = sorted(zip(nocs, cantus_ids), reverse=True)
        cantus_ids_sorted = [y for _, y in sorted_list]
        nocs_sorted = [x for x, _ in sorted_list]

        # return only NUM_SUGGESTIONS top chants
        print(cantus_ids_sorted[:NUM_SUGGESTIONS])
        print(nocs_sorted[:NUM_SUGGESTIONS])
        print("total suggestions: ", len(cantus_ids))

        suggested_chants = cantus_ids_sorted[:NUM_SUGGESTIONS]
        suggested_chants_dicts = []

        for i in range(NUM_SUGGESTIONS):
            try:
                suggested_chant = suggested_chants[i]  # suggested_chant is a CantusID
            except IndexError:
                # if the actual number of suggestions is less than NUM_SUGGESTIONS
                break
            # do a search in CI
            response = requests.get(
                "http://cantusindex.org/json-cid/{}".format(suggested_chant)
            )
            assert response.status_code == 200
            # parse the json export to a dict
            # response.json() # can't use this because of the BOM at the beginning of json export
            chant_dict = json.loads(response.text[1:])[0]
            # add number of occurence to the dict, so that we can display it easily
            chant_dict["noc"] = nocs_sorted[i]
            suggested_chants_dicts.append(chant_dict)
        return suggested_chants_dicts

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source_link"] = reverse("source-detail", args=[self.source_id])
        context["source"] = self.source
        try:
            previous_chant = Chant.objects.all().get(
                source=self.source,
                folio=self.latest_folio,
                sequence_number=self.latest_seq - 1,
            )
            context["previous_chant"] = previous_chant
            context["previous_chant_link"] = reverse(
                "chant-detail", args=[previous_chant.id]
            )
        except Chant.DoesNotExist:
            context["previous_chant"] = None
        print("other context done")
        context["suggested_chants"] = self.get_suggested_chants()
        print("suggesions done")
        return context

    def form_valid(self, form):
        """compute source, incipit; folio/sequence (if left empty)
        validate the form: add success/error message
        """
        # compute source
        form.instance.source = self.source  # same effect as the next line
        # form.instance.source = get_object_or_404(Source, pk=self.kwargs['source_pk'])

        # compute incipit, within 30 charactors, keep words complete
        words = form.instance.manuscript_full_text_std_spelling.split(" ")
        incipit = ""
        for word in words:
            new_incipit = incipit + word + " "
            if len(new_incipit) >= 30:
                break
            incipit = new_incipit

        form.instance.incipit = incipit.strip(" ")

        # if the folio field is left empty
        if form.instance.folio is None:
            form.instance.folio = self.latest_folio

        # if the sequence field is left empty
        if form.instance.sequence_number is None:
            form.instance.sequence_number = self.latest_seq

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
                "Chant with the same sequence and folio already exists in this source.",
            )

        if form.is_valid():
            messages.success(
                self.request,
                "Chant '" + form.instance.incipit + "' created successfully!",
            )
            return super().form_valid(form)
        else:
            return super().form_invalid(form)


class ChantDeleteView(DeleteView):
    """delete chant on chant-detail page"""

    model = Chant
    success_url = reverse_lazy("chant-list")
    template_name = "chant_confirm_delete.html"


class ChantUpdateView(UpdateView):
    model = Chant
    template_name = "chant_form.html"
    fields = "__all__"
    success_url = "/chants"


class CISearchView(TemplateView):
    """search in CI and write results in get_context_data
    now this is implemented as [send a search request to CI -> scrape the returned html table]
    But, it is possible to use CI json export.
    To do a text search on CI, use 'http://cantusindex.org/json-text/<text to search>'
    """

    template_name = "ci_search.html"

    def get_context_data(self, **kwargs):
        MAX_PAGE_NUMBER_CI = 5

        context = super().get_context_data(**kwargs)
        search_term = kwargs["search_term"]
        search_term = search_term.replace(" ", "+")  # for multiple keywords
        # Create empty list for the 3 types of info
        cantus_id = []
        genre = []
        full_text = []

        # scrape multiple pages
        pages = range(0, MAX_PAGE_NUMBER_CI)
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


class FullIndexView(TemplateView):
    template_name = "full_index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        source_id = self.request.GET.get("source")
        source = Source.objects.get(id=source_id)
        # 4064 is the id for the sequence database
        if source.segment.id == 4064:
            queryset = source.sequence_set.order_by("id")
        else:
            queryset = source.chant_set.order_by("id")

        context["source"] = source
        context["chants"] = queryset

        return context
