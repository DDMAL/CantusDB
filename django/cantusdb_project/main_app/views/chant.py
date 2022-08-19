import lxml.html as lh
import requests
import urllib
import json
from django.contrib import messages
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F, Q, QuerySet
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
from django.core.exceptions import PermissionDenied
from main_app.forms import ChantCreateForm, ChantEditForm, ChantProofreadForm, ChantEditSyllabificationForm
from main_app.models import Chant, Feast, Genre, Source, Sequence
from align_text_mel import *
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404
from next_chants import next_chants
from collections import Counter
from django.contrib.auth.mixins import UserPassesTestMixin



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
        
        # if the chant's source isn't published, only logged-in users should be able to view the chant's detail page
        source = chant.source
        if (source.published is False) and (not self.request.user.is_authenticated):
            raise PermissionDenied()

        # syllabification section
        if chant.volpiano:
            syls_melody = syllabize_melody(chant.volpiano)

            if chant.manuscript_syllabized_full_text:
                syls_text = syllabize_text(
                    chant.manuscript_syllabized_full_text, pre_syllabized=True
                )
            elif chant.manuscript_full_text:
                syls_text = syllabize_text(
                    chant.manuscript_full_text, pre_syllabized=False
                )
                syls_text, syls_melody = postprocess(syls_text, syls_melody)
            else:
                syls_text = syllabize_text(chant.incipit, pre_syllabized=False)
                syls_text, syls_melody = postprocess(syls_text, syls_melody)

            word_zip = align(syls_text, syls_melody)
            context["syllabized_text_with_melody"] = word_zip

        # some chants don't have a source, for those chants, stop here without further calculating
        # other context variables
        if not chant.source:
            return context

        # source navigation section
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
            # this will be a nested list of the following format:
            # [
            #   [feast_id_1, [chant, chant, ...]], 
            #   [feast_id_2, [chant, chant, ...]], 
            #   ...
            # ]
            feasts_chants = []
            for chant in chants_in_folio.order_by("sequence_number"):
                # if feasts_chants is empty, append a new list 
                if not feasts_chants:
                    # if the chant has a feast, append the following: [feast_id, []]
                    if chant.feast:
                        feasts_chants.append([chant.feast.id, []])
                    # else, append the following: ["no_feast", []]
                    else:
                        feasts_chants.append(["no_feast", []])
                else:
                    # if the chant has a feast and this feast id is different from the last appended lists' feast id,
                    # append a new list: [feast_id, []]
                    if chant.feast and (chant.feast.id != feasts_chants[-1][0]):
                        feasts_chants.append([chant.feast.id, []])
                    # if the chant doesn't have a feast and last appended list was for chants that had feast id,
                    # append a new list: ["no_feast", []]
                    elif not chant.feast and (feasts_chants[-1][0] != "no_feast"):
                        feasts_chants.append(["no_feast", []])
                # add the chant
                feasts_chants[-1][1].append(chant)

            # go through feasts_chants and replace feast_id with the corresponding Feast object
            for feast_chants in feasts_chants:
                # if there is no feast_id because the chant had no feast, assign a None object
                if feast_chants[0] == "no_feast":
                    feast_chants[0] = None
                    continue
                feast_chants[0] = Feast.objects.get(id=feast_chants[0])

            return feasts_chants

        context["feasts_current_folio"] = get_chants_with_feasts(chants_current_folio)

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

        return context


class ChantListView(ListView):
    """The view for the `Browse Chants` page.

    Displays a list of Chant objects, accessed with ``chants`` followed by a series of GET params

    ``GET`` parameters:
        ``source``: Filters by Source of Chant
        ``feast``: Filters by Feast of Chant
        ``search_text``: Filters by text of Chant
        ``genre``: Filters by genre of Chant
        ``folio``: Filters by folio of Chant
    """

    model = Chant
    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_list.html"

    def get_queryset(self):
        """Gather the chants to be displayed. 

        When in the `browse chants` page, there must be a source specified. 
        The chants in the specified source are filtered by a set of optional search parameters.

        Returns:
            queryset: The Chant objects to be displayed.
        """
        # when arriving at this page, the url must have a source specified
        source_id = self.request.GET.get("source")
        source = Source.objects.get(id=source_id)
        
        if (source.published is False) and (not self.request.user.is_authenticated):
            raise PermissionDenied()

        # optional search params
        feast_id = self.request.GET.get("feast")
        genre_id = self.request.GET.get("genre")
        folio = self.request.GET.get("folio")
        search_text = self.request.GET.get("search_text")

        # get all chants in the specified source
        chants = source.chant_set
        # filter the chants with optional search params
        if feast_id:
            chants = chants.filter(feast__id=feast_id)
        if genre_id:
            chants = chants.filter(genre__id=genre_id)
        if folio:
            chants = chants.filter(folio=folio)
        if search_text:
            search_text = search_text.replace("+", " ").strip(" ")
            chants = chants.filter(
                Q(manuscript_full_text_std_spelling__icontains=search_text)
                | Q(incipit__icontains=search_text)
                | Q(manuscript_full_text__icontains=search_text)
            )
        return chants.order_by("id")

    def get_context_data(self, **kwargs):
        def get_feast_selector_options(source, folios):
            """Generate folio-feast pairs as options for the feast selector

            Going through all chants in the source, folio by folio,
            a new entry (in the form of folio-feast) is added when the feast changes. 

            Args:
                source (Source object): The source that the user is browsing in.
                folios (list of strs): A list of folios in the source.

            Returns:
                zip object: A zip object combining a list of folios and Feast objects, to be unpacked in template.
            """
            # the two lists to be zipped
            feast_selector_feasts = []
            feast_selector_folios = []
            # get all chants in the source, select those that have a feast
            chants_in_source = (
                source.chant_set.exclude(feast=None)
                .order_by("folio", "sequence_number")
                .select_related("feast")
            )
            # initialize the feast selector options with the first chant in the source that has a feast
            first_feast_chant = chants_in_source.first()
            if not first_feast_chant:
                # if none of the chants in this source has a feast, return an empty zip
                folios_with_feasts = []
            else:
                # if there is at least one chant that has a feast
                current_feast = first_feast_chant.feast
                feast_selector_feasts.append(current_feast)
                current_folio = first_feast_chant.folio
                feast_selector_folios.append(current_folio)

                for folio in folios:
                    # get all chants on each folio
                    chants_on_folio = chants_in_source.filter(folio=folio)
                    for chant in chants_on_folio:
                        if chant.feast != current_feast:
                            # if the feast changes, add the new feast and the corresponding folio to the lists
                            feast_selector_feasts.append(chant.feast)
                            feast_selector_folios.append(folio)
                            # update the current_feast to track future changes
                            current_feast = chant.feast
                # as the two lists will always be of the same length, no need for zip,
                # just naively combine them
                # if we use zip, the returned generator will be exhausted in rendering templates, making it hard to test the returned value
                folios_with_feasts = [
                    (feast_selector_folios[i], feast_selector_feasts[i])
                    for i in range(len(feast_selector_folios))
                ]
            return folios_with_feasts

        context = super().get_context_data(**kwargs)
        # these are needed in the selectors on the left side of the page
        context["sources"] = Source.objects.order_by("siglum")
        context["feasts"] = Feast.objects.all().order_by("name")
        context["genres"] = Genre.objects.all().order_by("name")

        source_id = self.request.GET.get("source")
        source = Source.objects.get(id=source_id)
        context["source"] = source

        chants_in_source = source.chant_set
        if chants_in_source.count() == 0:
            # these are needed in the selectors and hyperlinks on the right side of the page
            # if there's no chant in the source, there should be no options in those selectors
            context["folios"] = None
            context["feasts_with_folios"] = None
            context["previous_folio"] = None
            context["next_folio"] = None
            return context

        # generate options for the folio selector on the right side of the page
        folios = (
            chants_in_source.values_list("folio", flat=True)
            .distinct()
            .order_by("folio")
        )
        context["folios"] = folios

        if self.request.GET.get("folio"):
            # if browsing chants on a specific folio
            folio = self.request.GET.get("folio")
            index = list(folios).index(folio)
            # get the previous and next folio, if available
            context["previous_folio"] = folios[index - 1] if index != 0 else None
            context["next_folio"] = (
                folios[index + 1] if index < len(folios) - 1 else None
            )

        # the options for the feast selector on the right, same as the source detail page
        context["feasts_with_folios"] = get_feast_selector_options(source, folios)
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
        chant_set = Chant.objects.filter(cantus_id=self.cantus_id)
        sequence_set = Sequence.objects.filter(cantus_id=self.cantus_id)
        display_unpublished = self.request.user.is_authenticated
        if not display_unpublished:
            chant_set = chant_set.filter(source__published=True)
            sequence_set = sequence_set.filter(source__published=True)
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

    If no ``GET`` parameters, returns empty queryset

    ``GET`` parameters:
        ``office``: Filters by Office of Chant
        ``genre``: Filters by Genre of Chant
        ``cantus_id``: Filters by the Cantus ID field of Chant
        ``mode``: Filters by mode of Chant
        ``position``: Filters by position of chant
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
        display_unpublished = self.request.user.is_authenticated
        # if the search is accessed by the global search bar
        if self.request.GET.get("search_bar"):
            chant_set = Chant.objects.filter(source__published=True)
            sequence_set = Sequence.objects.filter(source__published=True)
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
            # The field names should be keys in the "GET" QueryDict if the search button has been clicked,
            # even if the user put nothing into the search form and hit "apply" immediately.
            # In that case, we return the all chants + seqs filtered by the search form.
            # On the contrary, if the user just arrived at the search page, there should be no params in GET
            # In that case, we return an empty queryset.
            if not self.request.GET:
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
            if self.request.GET.get("position"):
                position = self.request.GET.get("position")
                q_obj_filter &= Q(position=position)
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
            if not display_unpublished:
                chant_set = Chant.objects.filter(source__published=True)
                sequence_set = Sequence.objects.filter(source__published=True)
            else:
                chant_set = Chant.objects
                sequence_set = Sequence.objects
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


class MelodySearchView(TemplateView):
    """
    Searches chants by the melody, accessed with `melody` (searching across all sources) 
    or `melody?src=<source_id>` (searching in one specific source)

    This view only pass in the context variable `source`

    The real searching happens at `views.ajax_melody_search`
    """

    template_name = "melody_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # if searching in a specific source, pass the source into context
        if self.request.GET.get("source"):
            context["source"] = Source.objects.get(id=self.request.GET.get("source"))
        return context


class ChantSearchMSView(ListView):
    """
    Searches chants/sequences in a certain manuscript, accessed with ``chant-search-ms/<int:source_pk>``

    This view uses the same template as ``ChantSearchView``

    If no ``GET`` parameters, returns empty queryset

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
        try:
            source = Source.objects.get(id=source_id)
            context["source"] = source
        except:
            raise Http404("This source does not exist")
        display_unpublished = self.request.user.is_authenticated
        if (source.published == False) and (not display_unpublished):
            raise PermissionDenied
        return context

    def get_queryset(self) -> QuerySet:
        # Create a Q object to filter the QuerySet of Chants
        q_obj_filter = Q()
        # If the "apply" button hasn't been clicked, return empty queryset
        if not self.request.GET:
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


class ChantCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create chants in a certain manuscript, accessed with `chant-create/<int:source_pk>`.

    This view displays the chant input form and provide access to 
    "input tool" and "chant suggestion tool" to facilitate the input process.
    """

    model = Chant
    template_name = "chant_create.html"
    form_class = ChantCreateForm
    pk_url_kwarg = 'source_pk'

    def test_func(self):
        user = self.request.user
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = get_object_or_404(Source, id=source_id)

        assigned_to_source = user.sources_user_can_edit.filter(id=source_id)

        # checks if the user is a project manager
        is_project_manager = user.groups.filter(name="project manager").exists()
        # checks if the user is an editor
        is_editor = user.groups.filter(name="editor").exists()
        # checks if the user is a contributor
        is_contributor = user.groups.filter(name="contributor").exists()

        if ((is_project_manager) 
            or (is_editor and assigned_to_source) 
            or (is_editor and source.created_by == user)  
            or (is_contributor and assigned_to_source)
            or (is_contributor and source.created_by == user)):
            return True
        else:
            return False

    # if success_url and get_success_url not specified, will direct to chant detail page
    def get_success_url(self):
        return reverse("chant-create", args=[self.source.id])

    def get_initial(self):
        """Get intial data from the latest chant in source.

        Some fields of the chant input form (`folio`, `feast`, `sequence_number`, and `image_link`) 
        are pre-populated upon loading. These fields are computed based on the latest chant in the source. 

        Returns:
            dict: field names and corresponding data
        """
        try:
            latest_chant = self.source.chant_set.latest("date_updated")
        except Chant.DoesNotExist:
            # if there is no chant in source, start with folio 001r, and sequence number 1
            return {
                "folio": "001r",
                "feast": "",
                "sequence_number": 1,
                "image_link": "",
            }
        latest_folio = latest_chant.folio if latest_chant.folio else "001r"
        latest_feast = latest_chant.feast.id if latest_chant.feast else ""
        latest_seq = latest_chant.sequence_number if latest_chant.sequence_number else 0
        latest_image = latest_chant.image_link if latest_chant.image_link else ""
        return {
            "folio": latest_folio,
            "feast": latest_feast,
            "sequence_number": latest_seq + 1,
            "image_link": latest_image,
        }

    def dispatch(self, request, *args, **kwargs):
        """Make sure the source specified in url exists before we display the form"""
        self.source = get_object_or_404(Source, pk=kwargs["source_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_suggested_chants(self):
        """based on the previous chant entered, get data and metadata on
        chants that follow the most recently entered chant in other manuscripts
        
        Returns:
            a list of dictionaries: for every potential chant,
            each dictionary includes data on that chant,
            taken from Cantus Index, as well as a count of how often
            that chant is found following the previous chant
        """

        # only displays the chants that occur most often
        NUM_SUGGESTIONS = 5
        try:
            latest_chant = self.source.chant_set.latest("date_updated")
        except Chant.DoesNotExist:
            return None

        cantus_id = latest_chant.cantus_id
        if cantus_id is None:
            return None

        suggested_chants = next_chants(cantus_id, display_unpublished=True)

        # sort by number of occurrences
        sorted_suggested_chants = sorted(suggested_chants,
                                         key=lambda id_count_pair: id_count_pair[1],
                                         reverse=True
                                         )
        # if there are more chants than NUM_SUGGESTIONS, remove chants that
        # don't frequently appear after the most recently entered chant
        trimmed_suggested_chants = sorted_suggested_chants[:NUM_SUGGESTIONS]

        def make_suggested_chant_dict(suggested_chant):
            """finds data on a chant with a particular cantusID, and adds a key "count" to that data

            Args:
                suggested_chant (tuple(str, int)): tuple containing the cantus ID of a chant,
                along with an int that represents the number of times the suggested chant follows
                another particular chant.

            Returns:
                dict: dictionary containing data for a specific chant, along with a count
                of how many times it appears after instances of the other particular chant.
            """
            sugg_chant_cantus_id, sugg_chant_count = suggested_chant
            # search Cantus Index
            response = requests.get(
                "http://cantusindex.org/json-cid/{}".format(sugg_chant_cantus_id)
            )
            assert response.status_code == 200
            # parse the json export to a dict
            # can't use response.json() because of the BOM at the beginning of json export
            chant_dict = json.loads(response.text[2:])[0]
            # add number of occurence to the dict, so that we can display it easily
            chant_dict["count"] = sugg_chant_count
            print(chant_dict)
            return chant_dict

        suggested_chants_dicts = [
            make_suggested_chant_dict(chant)
            for chant
            in trimmed_suggested_chants
            ]

        return suggested_chants_dicts

    def get_suggested_feasts(self):
        """based on the feast of the most recently edited chant, provide a list of suggested feasts that
        might follow the feast of that chant.

        Returns: a dictionary, with feast objects as keys and counts as values
        """
        try:
            latest_chant = self.source.chant_set.latest("date_updated")
        except Chant.DoesNotExist:
            return None

        current_feast = latest_chant.feast
        chants_that_end_feast = Chant.objects.filter(is_last_chant_in_feast = True)
        chants_that_end_current_feast = chants_that_end_feast.filter(feast=current_feast)
        next_chants = [chant.next_chant
            for chant
            in chants_that_end_current_feast
            ]
        next_feasts = [chant.feast
            for chant
            in next_chants
            if type(chant) is Chant # .get_next_chant() sometimes returns None
                and chant.feast is not None # some chants aren't associated with a feast
            ]
        print(next_feasts)
        feast_counts = Counter(next_feasts)
        print(feast_counts)
        sorted_feast_counts = dict( sorted(feast_counts.items(),
                           key=lambda item: item[1],
                           reverse=True))
        return sorted_feast_counts

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source"] = self.source
        try:
            context["previous_chant"] = self.source.chant_set.latest("date_updated")
        except Chant.DoesNotExist:
            context["previous_chant"] = None
        context["suggested_chants"] = self.get_suggested_chants()
        context["suggested_feasts"] = self.get_suggested_feasts()
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
            form.instance.created_by = self.request.user
            messages.success(
                self.request,
                "Chant '" + form.instance.incipit + "' created successfully!",
            )
            return super().form_valid(form)
        else:
            return super().form_invalid(form)


class ChantDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """The view for deleting a chant object

    This view is used in the chant-edit page, where an authorized user is allowed to
    edit or delete chants in a certain source. 
    """
    model = Chant
    template_name = "chant_confirm_delete.html"

    def test_func(self):
        user = self.request.user
        chant_id = self.kwargs.get(self.pk_url_kwarg)
        chant = get_object_or_404(Chant, id=chant_id)
        source = chant.source

        assigned_to_source = user.sources_user_can_edit.filter(id=source.id)

        # checks if the user is a project manager
        is_project_manager = user.groups.filter(name="project manager").exists()
        # checks if the user is an editor,
        is_editor = user.groups.filter(name="editor").exists()
        # checks if the user is a contributor,
        is_contributor = user.groups.filter(name="contributor").exists()

        if ((is_project_manager) 
            or (is_editor and assigned_to_source) 
            or (is_editor and source.created_by == user)  
            or (is_contributor and assigned_to_source)
            or (is_contributor and source.created_by == user)):
            return True
        else:
            return False

    def get_success_url(self):
        return reverse("source-edit-volpiano", args=[self.object.source.id])

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

class ChantEditVolpianoView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = "chant_edit.html"
    model = Chant
    form_class = ChantEditForm
    pk_url_kwarg = "source_id"

    def test_func(self):
        user = self.request.user
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = get_object_or_404(Source, id=source_id)

        assigned_to_source = user.sources_user_can_edit.filter(id=source_id)

        # checks if the user is a project manager
        is_project_manager = user.groups.filter(name="project manager").exists()
        # checks if the user is an editor,
        is_editor = user.groups.filter(name="editor").exists()
        # checks if the user is a contributor,
        is_contributor = user.groups.filter(name="contributor").exists()

        if ((is_project_manager) 
            or (is_editor and assigned_to_source) 
            or (is_editor and source.created_by == user)  
            or (is_contributor and assigned_to_source)
            or (is_contributor and source.created_by == user)):
            return True
        else:
            return False

    def get_queryset(self):
        """
            When a user visits the edit-chant page for a certain Source,
            there are 2 dropdowns on the right side of the page: one for folio, and the other for feast.

            When either a folio or a feast is selected, a list of Chants in the selected folio/feast will be rendered.

            Returns:
                a QuerySet of Chants in the Source, filtered by the optional search parameters.

            Note: the first folio is selected by default.
        """

        # when arriving at this page, the url must have a source specified
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = Source.objects.get(id=source_id)

        # optional search params
        feast_id = self.request.GET.get("feast")
        folio = self.request.GET.get("folio")

        # get all chants in the specified source
        chants = source.chant_set
        # filter the chants with optional search params
        if feast_id:
            chants = chants.filter(feast__id=feast_id)
        elif folio:
            chants = chants.filter(folio=folio)
        # if none of the optional search params are specified, the first folio in the source is selected by default
        else:
            folios = (
                chants.values_list("folio", flat=True)
                .distinct()
                .order_by("folio")
            )
            initial_folio = folios[0]
            chants = chants.filter(folio=initial_folio)
        self.queryset = chants
        return self.queryset
    
    def get_object(self):
        """
            If the Source has no Chant, an Http404 is raised.
            This is because there would be no Chant for the UpdateView to handle.

        Returns:
            the Chant that we wish to edit (specified by the Chant's pk)
        """
        queryset = self.get_queryset()
        if len(queryset) == 0:
            raise Http404("There are no chants associated with this source to edit")
        pk = self.request.GET.get("pk")
        # if a pk is not specified, this means that the user has not yet selected a Chant to edit
        # thus, we will not render the update form
        # instead, we will render the instructions page
        if not pk:
            pk = queryset.latest("date_created").pk
        queryset = queryset.filter(pk=pk)
        return queryset.get()

    def get_context_data(self, **kwargs):
        def get_feast_selector_options(source, folios):
            """Generate folio-feast pairs as options for the feast selector

            Going through all chants in the source, folio by folio,
            a new entry (in the form of folio-feast) is added when the feast changes. 

            Args:
                source (Source object): The source that the user is browsing in.
                folios (list of strs): A list of folios in the source.

            Returns:
                zip object: A zip object combining a list of folios and Feast objects, to be unpacked in template.
            """
            # the two lists to be zipped
            feast_selector_feasts = []
            feast_selector_folios = []
            # get all chants in the source, select those that have a feast
            chants_in_source = (
                source.chant_set.exclude(feast=None)
                .order_by("folio", "sequence_number")
                .select_related("feast")
            )
            # initialize the feast selector options with the first chant in the source that has a feast
            first_feast_chant = chants_in_source.first()
            if not first_feast_chant:
                # if none of the chants in this source has a feast, return an empty zip
                folios_with_feasts = []
            else:
                # if there is at least one chant that has a feast
                current_feast = first_feast_chant.feast
                feast_selector_feasts.append(current_feast)
                current_folio = first_feast_chant.folio
                feast_selector_folios.append(current_folio)

                for folio in folios:
                    # get all chants on each folio
                    chants_on_folio = chants_in_source.filter(folio=folio)
                    for chant in chants_on_folio:
                        if chant.feast != current_feast:
                            # if the feast changes, add the new feast and the corresponding folio to the lists
                            feast_selector_feasts.append(chant.feast)
                            feast_selector_folios.append(folio)
                            # update the current_feast to track future changes
                            current_feast = chant.feast
                # as the two lists will always be of the same length, no need for zip,
                # just naively combine them
                # if we use zip, the returned generator will be exhausted in rendering templates, making it hard to test the returned value
                folios_with_feasts = [
                    (feast_selector_folios[i], feast_selector_feasts[i])
                    for i in range(len(feast_selector_folios))
                ]
            return folios_with_feasts
            
        def get_chants_with_feasts(chants_in_folio):
            # this will be a nested list of the following format:
            # [
            #   [feast_id_1, [chant, chant, ...]], 
            #   [feast_id_2, [chant, chant, ...]], 
            #   ...
            # ]
            feasts_chants = []
            for chant in chants_in_folio.order_by("sequence_number"):
                # if feasts_chants is empty, append a new list 
                if not feasts_chants:
                    # if the chant has a feast, append the following: [feast_id, []]
                    if chant.feast:
                        feasts_chants.append([chant.feast.id, []])
                    # else, append the following: ["no_feast", []]
                    else:
                        feasts_chants.append(["no_feast", []])
                else:
                    # if the chant has a feast and this feast id is different from the last appended lists' feast id,
                    # append a new list: [feast_id, []]
                    if chant.feast and (chant.feast.id != feasts_chants[-1][0]):
                        feasts_chants.append([chant.feast.id, []])
                    # if the chant doesn't have a feast and last appended list was for chants that had feast id,
                    # append a new list: ["no_feast", []]
                    elif not chant.feast and (feasts_chants[-1][0] != "no_feast"):
                        feasts_chants.append(["no_feast", []])
                # add the chant
                feasts_chants[-1][1].append(chant)

            # go through feasts_chants and replace feast_id with the corresponding Feast object
            for feast_chants in feasts_chants:
                # if there is no feast_id because the chant had no feast, assign a None object
                if feast_chants[0] == "no_feast":
                    feast_chants[0] = None
                    continue
                feast_chants[0] = Feast.objects.get(id=feast_chants[0])

            return feasts_chants
        
        def get_chants_with_folios(chants_in_feast):
            # this will be a nested list of the following format:
            # [
            #   [folio_1, [chant, chant, ...]], 
            #   [folio_2, [chant, chant, ...]], 
            #   ...
            # ]
            folios_chants = []
            for chant in chants_in_feast.order_by("folio"):
                # if folios_chants is empty, or if your current chant in the for loop 
                # belongs in a different folio than the last chant,
                # append a new list with your current chant's folio
                if chant.folio and (not folios_chants or chant.folio != folios_chants[-1][0]):
                    folios_chants.append([chant.folio, []])
                # add the chant
                folios_chants[-1][1].append(chant)

            # sort the chants associated with a particular folio by sequence number
            for folio_chants in folios_chants:
                folio_chants[1].sort(key=lambda x: x.sequence_number)

            return folios_chants

        context = super().get_context_data(**kwargs)
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = Source.objects.get(id=source_id)
        context["source"] = source

        chants_in_source = source.chant_set

        # the following code block is sort of obsolete because if there is no Chant in the Source, a 404 will be raised
        if chants_in_source.count() == 0:
            # these are needed in the selectors and hyperlinks on the right side of the page
            # if there's no chant in the source, there should be no options in those selectors
            context["folios"] = None
            context["feasts_with_folios"] = None
            context["previous_folio"] = None
            context["next_folio"] = None
            return context

        # generate options for the folio selector on the right side of the page
        folios = (
            chants_in_source.values_list("folio", flat=True)
            .distinct()
            .order_by("folio")
        )
        context["folios"] = folios
        # the options for the feast selector on the right, same as the source detail page
        context["feasts_with_folios"] = get_feast_selector_options(source, folios)

        # the user has selected a folio, or,
        # they have just navigated to the edit-chant page (where the first folio gets selected by default)
        if self.request.GET.get("folio") or (not self.request.GET.get("folio") and not self.request.GET.get("feast")):
            # if browsing chants on a specific folio
            if self.request.GET.get("folio"):
                folio = self.request.GET.get("folio")
            else:
                folio = folios[0]
                # will be used in the template to pre-select the first folio in the drop-down
                context["initial_GET_folio"] = folio
            index = list(folios).index(folio)
            # get the previous and next folio, if available
            context["previous_folio"] = folios[index - 1] if index != 0 else None
            context["next_folio"] = (
                folios[index + 1] if index < len(folios) - 1 else None
            )
            # if there is a "folio" query parameter, it means the user has chosen a specific folio
            # need to render a list of chants, ordered by sequence number and grouped by feast
            context["feasts_current_folio"] = get_chants_with_feasts(self.queryset)
        
        elif self.request.GET.get("feast"):
            # if there is a "feast" query parameter, it means the user has chosen a specific feast
            # need to render a list of chants, grouped and ordered by folio and within each group,
            # ordered by sequence number
            context["folios_current_feast"] = get_chants_with_folios(self.queryset)

        # this boolean lets us decide whether to show the user the instructions or the editing form
        # if the pk hasn't been specified, a user hasn't selected a specific chant they want to edit
        # if so, we should display the instructions
        pk = self.request.GET.get("pk")
        pk_specified = bool(pk)
        context["pk_specified"] = pk_specified

        # provide a suggested_fulltext for situations in which a chant has no
        # manuscript_full_text_std_spelling
        context["suggested_fulltext"] = ""
        if pk_specified:
            current_chant = Chant.objects.filter(pk=pk).first()
            cantus_id = current_chant.cantus_id

            request = requests.get(
                    "http://cantusindex.org/json-cid/{}".format(cantus_id)
            )
            context["suggested_fulltext"] = json.loads(request.text[2:])[0]["fulltext"]

        chant = self.get_object()

        # Preview of melody and text:
        # in the old CantusDB,
        # 'manuscript_syllabized_full_text' exists => preview constructed from 'manuscript_syllabized_full_text'
        # no 'manuscript_syllabized_full_text', but 'manuscript_full_text' exists => preview constructed from 'manuscript_full_text'
        # no 'manuscript_syllabized_full_text' and no 'manuscript_full_text' => preview constructed from 'manuscript_full_text_std_spelling'

        if chant.volpiano:
            syls_melody = syllabize_melody(chant.volpiano)

            if chant.manuscript_syllabized_full_text:
                syls_text = syllabize_text(
                    chant.manuscript_syllabized_full_text, pre_syllabized=True
                )
            elif chant.manuscript_full_text:
                syls_text = syllabize_text(
                    chant.manuscript_full_text, pre_syllabized=False
                )
                syls_text, syls_melody = postprocess(syls_text, syls_melody)
            elif chant.manuscript_full_text_std_spelling:
                syls_text = syllabize_text(chant.manuscript_full_text_std_spelling, pre_syllabized=False)
                syls_text, syls_melody = postprocess(syls_text, syls_melody)

            word_zip = align(syls_text, syls_melody)
            context["syllabized_text_with_melody"] = word_zip

        return context
    
    def form_valid(self, form):
        if form.is_valid():
            form.instance.last_updated_by = self.request.user
            messages.success(
                self.request,
                "Chant updated successfully!",
            )
            return super().form_valid(form)
        else:
            return super().form_invalid(form)

    def get_success_url(self):
        # stay on the same page after save
        return self.request.get_full_path()

class ChantProofreadView(ChantEditVolpianoView):
    template_name = "chant_proofread.html"
    model = Chant
    form_class = ChantProofreadForm
    pk_url_kwarg = "source_id"

    def test_func(self):
        user = self.request.user
        source_id = self.kwargs.get(self.pk_url_kwarg)

        assigned_to_source = user.sources_user_can_edit.filter(id=source_id)

        # checks if the user is a project manager
        is_project_manager = user.groups.filter(name="project manager").exists()
        # checks if the user is an editor,
        is_editor = user.groups.filter(name="editor").exists()

        if (is_project_manager) or (is_editor and assigned_to_source):
            return True
        else:
            return False

class ChantEditSyllabificationView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = "chant_syllabification_edit.html"
    model = Chant
    context_object_name = "chant"
    form_class = ChantEditSyllabificationForm
    pk_url_kwarg = "chant_id"

    def test_func(self):
        chant = self.get_object()
        source = chant.source
        user = self.request.user

        assigned_to_source = user.sources_user_can_edit.filter(id=source.id)

        # checks if the user is a project manager
        is_project_manager = user.groups.filter(name="project manager").exists()
        # checks if the user is an editor,
        is_editor = user.groups.filter(name="editor").exists()
        # checks if the user is a contributor,
        is_contributor = user.groups.filter(name="contributor").exists()

        if ((is_project_manager)
            or (is_editor and assigned_to_source)
            or (is_editor and source.created_by == user)
            or (is_contributor and assigned_to_source)
            or (is_contributor and source.created_by == user)):
            return True
        else:
            return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chant = self.get_object()

        # Preview of melody and text:
        # in the old CantusDB,
        # 'manuscript_syllabized_full_text' exists => preview constructed from 'manuscript_syllabized_full_text'
        # no 'manuscript_syllabized_full_text', but 'manuscript_full_text' exists => preview constructed from 'manuscript_full_text'
        # no 'manuscript_syllabized_full_text' and no 'manuscript_full_text' => preview constructed from 'manuscript_full_text_std_spelling'

        if chant.volpiano:
            syls_melody = syllabize_melody(chant.volpiano)

            if chant.manuscript_syllabized_full_text:
                syls_text = syllabize_text(
                    chant.manuscript_syllabized_full_text, pre_syllabized=True
                )
            elif chant.manuscript_full_text:
                syls_text = syllabize_text(
                    chant.manuscript_full_text, pre_syllabized=False
                )
                syls_text, syls_melody = postprocess(syls_text, syls_melody)
            elif chant.manuscript_full_text_std_spelling:
                syls_text = syllabize_text(chant.manuscript_full_text_std_spelling, pre_syllabized=False)
                syls_text, syls_melody = postprocess(syls_text, syls_melody)

            word_zip = align(syls_text, syls_melody)
            context["syllabized_text_with_melody"] = word_zip

        return context

    def form_valid(self, form):
        form.instance.last_updated_by = self.request.user
        messages.success(
            self.request,
            "Syllabification updated successfully!",
        )
        return super().form_valid(form)

    def get_success_url(self):
        # stay on the same page after save
        return self.request.get_full_path()
