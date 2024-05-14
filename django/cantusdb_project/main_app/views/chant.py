import urllib
from collections import Counter
from typing import Optional, Iterator, cast

from volpiano_display_utilities.cantus_text_syllabification import (
    syllabify_text,
    flatten_syllabified_text,
)
from volpiano_display_utilities.text_volpiano_alignment import align_text_and_volpiano

from django.contrib import messages
from django.db.models import Q, QuerySet
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)
from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404

from django.contrib.auth.mixins import UserPassesTestMixin

from main_app.forms import (
    ChantCreateForm,
    ChantEditForm,
    ChantEditSyllabificationForm,
)
from main_app.models import (
    Chant,
    Feast,
    Genre,
    Source,
    Sequence,
    Office,
)
from main_app.permissions import (
    user_can_edit_chants_in_source,
    user_can_proofread_chant,
    user_can_view_chant,
)

from cantusindex import get_suggested_chants, get_suggested_fulltext

CHANT_SEARCH_TEMPLATE_VALUES: tuple[str, ...] = (
    # for views that use chant_search.html, this allows them to
    # fetch only those values needed for rendering the template
    "id",
    "folio",
    "search_vector",
    "incipit",
    "manuscript_full_text_std_spelling",
    "position",
    "cantus_id",
    "mode",
    "manuscript_full_text",
    "volpiano",
    "image_link",
    "source__id",
    "source__title",
    "source__siglum",
    "feast__id",
    "feast__description",
    "feast__name",
    "office__id",
    "office__description",
    "office__name",
    "genre__id",
    "genre__description",
    "genre__name",
)


def get_feast_selector_options(source: Source) -> list[tuple[str, int, str]]:
    """Generate folio-feast pairs as options for the feast selector

    Going through all chants in the source, folio by folio,
    a new entry (in the form of folio-feast) is added when the feast changes.

    Args:
        source (Source object): The source that the user is browsing in.

    Returns:
        list of tuples: A list of folios and Feast objects, to be unpacked in template.
    """
    folios_feasts_iter: Iterator[tuple[Optional[str], int, str]] = (
        source.chant_set.exclude(feast=None)
        .order_by("folio", "c_sequence")
        .values_list("folio", "feast_id", "feast__name")
        .iterator()
    )
    # Cast because we know, by restrictions on chant create form, that
    # folio won't be None
    folios_feasts_list = cast(list[tuple[str, int, str]], list(folios_feasts_iter))
    # De-dupe query set while maintaining order
    deduped_folios_feasts_lists = list(dict.fromkeys(folios_feasts_list))
    return deduped_folios_feasts_lists


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
        user = self.request.user
        source = chant.source

        # if the chant's source isn't published, only logged-in users should be able to
        # view the chant's detail page
        if not user_can_view_chant(user, chant):
            raise PermissionDenied()

        context["user_can_edit_chant"] = user_can_edit_chants_in_source(user, source)

        # syllabification section
        if chant.volpiano:
            has_syl_text = bool(chant.manuscript_syllabized_full_text)
            text_and_mel, _ = align_text_and_volpiano(
                chant.get_best_text_for_syllabizing(),
                chant.volpiano,
                text_presyllabified=has_syl_text,
            )
            context["syllabized_text_with_melody"] = text_and_mel

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
            for chant in chants_in_folio.order_by("c_sequence"):
                # if feasts_chants is empty, append a new list
                if not feasts_chants:
                    # if the chant has a feast, append the following: [feast_id, []]
                    if chant.feast:
                        feasts_chants.append([chant.feast.id, []])
                    # else, append the following: ["no_feast", []]
                    else:
                        feasts_chants.append(["no_feast", []])
                else:
                    # if the chant has a feast and this feast id is different from the last appended
                    # lists' feast id, append a new list: [feast_id, []]
                    if chant.feast and (chant.feast.id != feasts_chants[-1][0]):
                        feasts_chants.append([chant.feast.id, []])
                    # if the chant doesn't have a feast and last appended list was for chants that
                    # had feast id, append a new list: ["no_feast", []]
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
        chant_set = Chant.objects.filter(cantus_id=self.cantus_id).select_related(
            "source", "office", "genre", "feast"
        )
        sequence_set = Sequence.objects.filter(cantus_id=self.cantus_id).select_related(
            "source", "office", "genre", "feast"
        )
        display_unpublished = self.request.user.is_authenticated
        if not display_unpublished:
            chant_set = chant_set.filter(source__published=True)
            sequence_set = sequence_set.filter(source__published=True)
        # the union operation turns sequences into chants, the resulting queryset contains only
        # "chant" objects this forces us to do something special on the template to render correct
        # absolute url for sequences
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
        context["offices"] = Office.objects.all().order_by("name").values("id", "name")
        context["order"] = self.request.GET.get("order")
        context["sort"] = self.request.GET.get("sort")

        # build a url containing all the search parameters, excluding ordering parameters.
        # this way, when someone clicks on a column heading, we can append the ordering parameters
        # while retaining the search parameters
        current_url: str = self.request.path
        search_parameters: list[str] = []

        search_op: Optional[str] = self.request.GET.get("op")
        if search_op:
            search_parameters.append(f"op={search_op}")
        search_keyword: Optional[str] = self.request.GET.get("keyword")
        if search_keyword:
            search_parameters.append(f"keyword={search_keyword}")
            context["keyword"] = search_keyword
        search_office: Optional[str] = self.request.GET.get("office")
        if search_office:
            search_parameters.append(f"office={search_office}")
        search_genre: Optional[str] = self.request.GET.get("genre")
        if search_genre:
            search_parameters.append(f"genre={search_genre}")
        search_cantus_id: Optional[str] = self.request.GET.get("cantus_id")
        if search_cantus_id:
            search_parameters.append(f"cantus_id={search_cantus_id}")
        search_mode: Optional[str] = self.request.GET.get("mode")
        if search_mode:
            search_parameters.append(f"mode={search_mode}")
        search_feast: Optional[str] = self.request.GET.get("feast")
        if search_feast:
            search_parameters.append(f"feast={search_feast}")
        search_position: Optional[str] = self.request.GET.get("position")
        if search_position:
            search_parameters.append(f"position={search_position}")
        search_melodies: Optional[str] = self.request.GET.get("melodies")
        if search_melodies:
            search_parameters.append(f"melodies={search_melodies}")
        search_bar: Optional[str] = self.request.GET.get("search_bar")
        if search_bar:
            search_parameters.append(f"search_bar={search_bar}")

        url_with_search_params: str = current_url + "?"
        if search_parameters:
            joined_search_parameters: str = "&".join(search_parameters)
            url_with_search_params += joined_search_parameters

        context["url_with_search_params"] = url_with_search_params

        return context

    def get_queryset(self) -> QuerySet:
        # if user has just arrived on the Chant Search page, there will be no
        # GET parameters.
        if not self.request.GET:
            return Chant.objects.none()

        # Create a Q object to filter the QuerySet of Chants
        q_obj_filter = Q()
        display_unpublished = self.request.user.is_authenticated
        # if the search is accessed by the global search bar
        if self.request.GET.get("search_bar"):
            if display_unpublished:
                chant_set = Chant.objects.all()
                sequence_set = Sequence.objects.all()
            else:
                chant_set = Chant.objects.filter(source__published=True)
                sequence_set = Sequence.objects.filter(source__published=True)

            search_bar_term_contains_digits = any(
                map(str.isdigit, self.request.GET.get("search_bar"))
            )
            if search_bar_term_contains_digits:
                # if search bar is doing Cantus ID search
                cantus_id = self.request.GET.get("search_bar")
                q_obj_filter &= Q(cantus_id__icontains=cantus_id)
                chant_set = chant_set.filter(q_obj_filter).values(
                    *CHANT_SEARCH_TEMPLATE_VALUES
                )
                sequence_set = sequence_set.filter(q_obj_filter).values(
                    *CHANT_SEARCH_TEMPLATE_VALUES
                )
                queryset = chant_set.union(sequence_set, all=True)
            else:
                # if search bar is doing incipit search
                search_term = self.request.GET.get("search_bar")
                ms_spelling_filter = Q(manuscript_full_text__istartswith=search_term)
                std_spelling_filter = Q(
                    manuscript_full_text_std_spelling__istartswith=search_term
                )
                incipit_filter = Q(incipit__istartswith=search_term)
                search_term_filter = (
                    ms_spelling_filter | std_spelling_filter | incipit_filter
                )
                chant_set = chant_set.filter(search_term_filter).values(
                    *CHANT_SEARCH_TEMPLATE_VALUES
                )
                sequence_set = sequence_set.filter(search_term_filter).values(
                    *CHANT_SEARCH_TEMPLATE_VALUES
                )
                queryset = chant_set.union(sequence_set, all=True)
            queryset = queryset.order_by("source__siglum", "id")

        else:
            # The field names should be keys in the "GET" QueryDict if the search button has been
            # clicked, even if the user put nothing into the search form and hit "apply"
            # immediately. In that case, we return the all chants + seqs filtered by the search
            # form. For every GET parameter other than incipit, add to the Q object
            if self.request.GET.get("office"):
                office_id = self.request.GET.get("office")
                q_obj_filter &= Q(office__id=office_id)
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
            if self.request.GET.get("feast"):
                feast = self.request.GET.get("feast")
                # This will match any feast whose name contains the feast parameter
                # as a substring
                feasts = Feast.objects.filter(name__icontains=feast)
                q_obj_filter &= Q(feast__in=feasts)
            order_get_param: Optional[str] = self.request.GET.get("order")
            sort_get_param: Optional[str] = self.request.GET.get("sort")

            order_param_options = (
                "incipit",
                "office",
                "genre",
                "cantus_id",
                "mode",
                "has_fulltext",
                "has_melody",
                "has_image",
            )
            if order_get_param in order_param_options:
                if order_get_param == "has_fulltext":
                    order = "manuscript_full_text"
                elif order_get_param == "has_melody":
                    order = "volpiano"
                elif order_get_param == "has_image":
                    order = "image_link"
                else:
                    order = order_get_param
            else:
                order = "source__siglum"

            # sort values: "asc" and "desc". Default is "asc"
            if sort_get_param and sort_get_param == "desc":
                order = f"-{order}"

            if not display_unpublished:
                chant_set: QuerySet = Chant.objects.filter(source__published=True)
                sequence_set: QuerySet = Sequence.objects.filter(source__published=True)
            else:
                chant_set: QuerySet = Chant.objects.all()
                sequence_set: QuerySet = Sequence.objects.all()
            # Filter the QuerySet with Q object
            chant_set = chant_set.filter(q_obj_filter)
            sequence_set = sequence_set.filter(q_obj_filter)
            # Fetch only the values necessary for rendering the template
            chant_set = chant_set.values(*CHANT_SEARCH_TEMPLATE_VALUES)
            sequence_set = sequence_set.values(*CHANT_SEARCH_TEMPLATE_VALUES)
            # Finally, do keyword searching over the querySet
            if self.request.GET.get("keyword"):
                keyword = self.request.GET.get("keyword")
                operation: Optional[str] = self.request.GET.get("op")
                if operation and operation == "contains":
                    ms_spelling_filter = Q(manuscript_full_text__icontains=keyword)
                    std_spelling_filter = Q(
                        manuscript_full_text_std_spelling__icontains=keyword
                    )
                    incipit_filter = Q(incipit__icontains=keyword)
                else:
                    ms_spelling_filter = Q(manuscript_full_text__istartswith=keyword)
                    std_spelling_filter = Q(
                        manuscript_full_text_std_spelling__istartswith=keyword
                    )
                    incipit_filter = Q(incipit__istartswith=keyword)
                keyword_filter = (
                    ms_spelling_filter | std_spelling_filter | incipit_filter
                )
                chant_set = chant_set.filter(keyword_filter)
                sequence_set = sequence_set.filter(keyword_filter)

            # once unioned, the queryset cannot be filtered/annotated anymore, so we put
            # union to the last
            queryset = chant_set.union(sequence_set, all=True)
            queryset = queryset.order_by(order, "id")

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
    Searches chants/sequences in a certain manuscript, accessed with
    ``chant-search-ms/<int:source_pk>``

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
        context["offices"] = Office.objects.all().order_by("name").values("id", "name")
        context["order"] = self.request.GET.get("order")
        context["sort"] = self.request.GET.get("sort")
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

        current_url = self.request.path
        search_parameters = []

        search_op = self.request.GET.get("op")
        if search_op:
            search_parameters.append(f"op={search_op}")
        search_keyword = self.request.GET.get("keyword")
        if search_keyword:
            search_parameters.append(f"keyword={search_keyword}")
        search_office = self.request.GET.get("office")
        if search_office:
            search_parameters.append(f"office={search_office}")
        search_genre = self.request.GET.get("genre")
        if search_genre:
            search_parameters.append(f"genre={search_genre}")
        search_cantus_id = self.request.GET.get("cantus_id")
        if search_cantus_id:
            search_parameters.append(f"cantus_id={search_cantus_id}")
        search_mode = self.request.GET.get("mode")
        if search_mode:
            search_parameters.append(f"mode={search_mode}")
        search_feast = self.request.GET.get("feast")
        if search_feast:
            search_parameters.append(f"feast={search_feast}")
        search_position = self.request.GET.get("position")
        if search_position:
            search_parameters.append(f"position={search_position}")
        search_melodies = self.request.GET.get("melodies")
        if search_melodies:
            search_parameters.append(f"melodies={search_melodies}")

        if search_parameters:
            joined_search_parameters = "&".join(search_parameters)
            url_with_search_params = current_url + "?" + joined_search_parameters
        else:
            url_with_search_params = current_url + "?"

        context["url_with_search_params"] = url_with_search_params
        return context

    def get_queryset(self) -> QuerySet:
        # Create a Q object to filter the QuerySet of Chants
        q_obj_filter = Q()
        # If the "apply" button hasn't been clicked, return empty queryset
        if not self.request.GET:
            return Chant.objects.none()
        # For every GET parameter other than incipit, add to the Q object
        if self.request.GET.get("office"):
            office_id = self.request.GET.get("office")
            q_obj_filter &= Q(office__id=office_id)
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
        if self.request.GET.get("order"):
            if self.request.GET.get("order") == "siglum":
                order = "siglum"
            elif self.request.GET.get("order") == "incipit":
                order = "incipit"
            elif self.request.GET.get("order") == "office":
                order = "office"
            elif self.request.GET.get("order") == "genre":
                order = "genre"
            elif self.request.GET.get("order") == "cantus_id":
                order = "cantus_id"
            elif self.request.GET.get("order") == "mode":
                order = "mode"
            elif self.request.GET.get("order") == "has_fulltext":
                order = "manuscript_full_text"
            elif self.request.GET.get("order") == "has_melody":
                order = "volpiano"
            elif self.request.GET.get("order") == "has_image":
                order = "image_link"
            else:
                order = "siglum"
        else:
            order = "siglum"
        if self.request.GET.get("sort"):
            if self.request.GET.get("sort") == "asc":
                order = order
            elif self.request.GET.get("sort") == "desc":
                order = "-" + order

        source_id = self.kwargs["source_pk"]
        source = Source.objects.get(id=source_id)
        queryset = (
            source.sequence_set if source.segment.id == 4064 else source.chant_set
        )
        # Filter the QuerySet with Q object
        queryset = queryset.filter(q_obj_filter)
        # Fetch only the values necessary for rendering the template
        queryset = queryset.values(*CHANT_SEARCH_TEMPLATE_VALUES)
        # Finally, do keyword searching over the QuerySet
        if self.request.GET.get("keyword"):
            keyword = self.request.GET.get("keyword")
            operation = self.request.GET.get("op")
            # the operation parameter can be "contains" or "starts_with"
            if operation == "contains":
                ms_spelling_filter = Q(manuscript_full_text__icontains=keyword)
                std_spelling_filter = Q(
                    manuscript_full_text_std_spelling__icontains=keyword
                )
                incipit_filter = Q(incipit__icontains=keyword)
            else:
                ms_spelling_filter = Q(manuscript_full_text__istartswith=keyword)
                std_spelling_filter = Q(
                    manuscript_full_text_std_spelling__istartswith=keyword
                )
                incipit_filter = Q(incipit__istartswith=keyword)
            keyword_filter = ms_spelling_filter | std_spelling_filter | incipit_filter
            queryset = queryset.filter(keyword_filter)
        # ordering with the folio string gives wrong order
        # old cantus is also not strictly ordered by folio (there are outliers)
        # so we order by id for now, which is the order that the chants are entered into the DB
        queryset = queryset.order_by(order, "id")
        return queryset


class ChantCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create chants in a certain manuscript, accessed with `chant-create/<int:source_pk>`.

    This view displays the chant input form and provide access to
    "input tool" and "chant suggestion tool" to facilitate the input process.
    """

    model = Chant
    template_name = "chant_create.html"
    form_class = ChantCreateForm
    pk_url_kwarg = "source_pk"

    def test_func(self):
        user = self.request.user
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = get_object_or_404(Source, id=source_id)

        return user_can_edit_chants_in_source(user, source)

    # if success_url and get_success_url not specified, will direct to chant detail page
    def get_success_url(self):
        return reverse("chant-create", args=[self.source.id])

    def get_initial(self):
        """Get intial data from the latest chant in source.

        Some fields of the chant input form (`folio`, `feast`, `c_sequence`, and `image_link`)
        are pre-populated upon loading. These fields are computed based on the latest chant in
        the source.

        Returns:
            dict: field names and corresponding data
        """
        try:
            latest_chant = self.source.chant_set.latest("date_updated")
        except Chant.DoesNotExist:
            # if there is no chant in source, start with folio 001r, and c_sequence 1
            return {
                "folio": "001r",
                "feast": "",
                "c_sequence": 1,
                "image_link": "",
            }
        latest_folio = latest_chant.folio if latest_chant.folio else "001r"
        latest_feast = latest_chant.feast.id if latest_chant.feast else ""
        latest_office = latest_chant.office.id if latest_chant.office else ""
        latest_seq = (
            latest_chant.c_sequence if latest_chant.c_sequence is not None else 0
        )
        latest_image = latest_chant.image_link if latest_chant.image_link else ""
        return {
            "folio": latest_folio,
            "feast": latest_feast,
            "office": latest_office,
            "c_sequence": latest_seq + 1,
            "image_link": latest_image,
        }

    def dispatch(self, request, *args, **kwargs):
        """Make sure the source specified in url exists before we display the form"""
        self.source = get_object_or_404(Source, pk=kwargs["source_pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_suggested_feasts(self):
        """based on the feast of the most recently edited chant, provide a
        list of suggested feasts that might follow the feast of that chant.

        Returns: a dictionary, with feast objects as keys and counts as values
        """
        try:
            latest_chant = self.source.chant_set.latest("date_updated")
        except Chant.DoesNotExist:
            return None

        current_feast = latest_chant.feast
        chants_that_end_feast = Chant.objects.filter(is_last_chant_in_feast=True)
        chants_that_end_current_feast = chants_that_end_feast.filter(
            feast=current_feast
        )
        next_chants = [chant.next_chant for chant in chants_that_end_current_feast]
        next_feasts = [
            chant.feast
            for chant in next_chants
            if type(chant) is Chant  # .get_next_chant() sometimes returns None
            and chant.feast is not None  # some chants aren't associated with a feast
        ]
        feast_counts = Counter(next_feasts)
        sorted_feast_counts = dict(
            sorted(feast_counts.items(), key=lambda item: item[1], reverse=True)
        )
        return sorted_feast_counts

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source"] = self.source
        previous_chant: Optional[Chant] = None
        try:
            previous_chant = self.source.chant_set.latest("date_updated")
        except Chant.DoesNotExist:
            pass
        context["previous_chant"] = previous_chant
        context["suggested_feasts"] = self.get_suggested_feasts()

        previous_cantus_id: Optional[str] = None
        if previous_chant:
            previous_cantus_id = previous_chant.cantus_id

        suggested_chants: Optional[list[dict]] = None
        if previous_cantus_id:
            suggested_chants = get_suggested_chants(previous_cantus_id)
        context["suggested_chants"] = suggested_chants

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
                c_sequence=form.instance.c_sequence,
            )
            .exists()
        ):
            form.add_error(
                None,
                "Chant with the same sequence and folio already exists in this source.",
            )

        if form.is_valid():
            form.instance.created_by = self.request.user
            form.instance.last_updated_by = self.request.user
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
    template_name = "chant_delete.html"

    def test_func(self):
        user = self.request.user
        chant_id = self.kwargs.get(self.pk_url_kwarg)
        chant = get_object_or_404(Chant, id=chant_id)
        source = chant.source

        return user_can_edit_chants_in_source(user, source)

    def get_success_url(self):
        return reverse("source-edit-chants", args=[self.object.source.id])


class SourceEditChantsView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = "chant_edit.html"
    model = Chant
    form_class = ChantEditForm
    pk_url_kwarg = "source_id"

    def test_func(self):
        user = self.request.user
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = get_object_or_404(Source, id=source_id)

        return user_can_edit_chants_in_source(user, source)

    def get_queryset(self):
        """
        When a user visits the edit-chant page for a certain Source,
        there are 2 dropdowns on the right side of the page: one for folio, and the other for feast.

        When either a folio or a feast is selected, a list of Chants in the selected folio/feast will
        be rendered.

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
        if not source.chant_set.exists():
            # return empty queryset
            return chants.all()
        # filter the chants with optional search params
        if feast_id:
            chants = chants.filter(feast__id=feast_id)
        elif folio:
            chants = chants.filter(folio=folio)
        # if none of the optional search params are specified, the first folio in the
        # source is selected by default
        else:
            folios = chants.values_list("folio", flat=True).distinct().order_by("folio")
            if not folios:
                # if the source has no chants (conceivable), or if it has chants but
                # none of them have folios specified (we don't really expect this to happen)
                raise Http404
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
        if queryset.count() == 0:
            return None
        pk = self.request.GET.get("pk")
        # if a pk is not specified, this means that the user has not yet selected a Chant to edit
        # thus, we will not render the update form
        # instead, we will render the instructions page
        if not pk:
            pk = queryset.latest("date_created").pk
        queryset = queryset.filter(pk=pk)
        return queryset.get()

    def get_context_data(self, **kwargs):
        def get_chants_with_feasts(chants_in_folio):
            # this will be a nested list of the following format:
            # [
            #   [feast_id_1, [chant, chant, ...]],
            #   [feast_id_2, [chant, chant, ...]],
            #   ...
            # ]
            feasts_chants = []
            for chant in chants_in_folio.order_by("c_sequence"):
                # if feasts_chants is empty, append a new list
                if not feasts_chants:
                    # if the chant has a feast, append the following: [feast_id, []]
                    if chant.feast:
                        feasts_chants.append([chant.feast.id, []])
                    # else, append the following: ["no_feast", []]
                    else:
                        feasts_chants.append(["no_feast", []])
                else:
                    # if the chant has a feast and this feast id is different from the last appended
                    # lists' feast id, append a new list: [feast_id, []]
                    if chant.feast and (chant.feast.id != feasts_chants[-1][0]):
                        feasts_chants.append([chant.feast.id, []])
                    # if the chant doesn't have a feast and last appended list was for chants that
                    # had feast id, append a new list: ["no_feast", []]
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
                if chant.folio and (
                    not folios_chants or chant.folio != folios_chants[-1][0]
                ):
                    folios_chants.append([chant.folio, []])
                # add the chant
                folios_chants[-1][1].append(chant)

            # sort the chants associated with a particular folio by c_sequence
            for folio_chants in folios_chants:
                folio_chants[1].sort(key=lambda x: x.c_sequence)

            return folios_chants

        context = super().get_context_data(**kwargs)
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = Source.objects.get(id=source_id)
        context["source"] = source

        chants_in_source = source.chant_set

        # the following code block is sort of obsolete because if there is no Chant
        # in the Source, a 404 will be raised
        if not chants_in_source.exists():
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
        context["feasts_with_folios"] = get_feast_selector_options(source)

        if self.request.GET.get("feast"):
            # if there is a "feast" query parameter, it means the user has chosen a specific feast
            # need to render a list of chants, grouped and ordered by folio and within each group,
            # ordered by c_sequence
            context["folios_current_feast"] = get_chants_with_folios(self.queryset)
        else:
            # the user has selected a folio, or,
            # they have just navigated to the edit-chant page (where the first folio gets
            # selected by default)
            if self.request.GET.get("folio"):
                # if browsing chants on a specific folio
                folio = self.request.GET.get("folio")
            else:
                folio = folios[0]
                # will be used in the template to pre-select the first folio in the drop-down
                context["initial_GET_folio"] = folio
            try:
                index = list(folios).index(folio)
            except ValueError:
                raise Http404("No chants within source match the specified folio")
            # get the previous and next folio, if available
            context["previous_folio"] = folios[index - 1] if index != 0 else None
            context["next_folio"] = (
                folios[index + 1] if index < len(folios) - 1 else None
            )
            # if there is a "folio" query parameter, it means the user has chosen a specific folio
            # need to render a list of chants, ordered by c_sequence and grouped by feast
            context["feasts_current_folio"] = get_chants_with_feasts(self.queryset)

        # this boolean lets us decide whether to show the user the instructions or the editing form
        # if the pk hasn't been specified, a user hasn't selected a specific chant they want to edit
        # if so, we should display the instructions
        pk = self.request.GET.get("pk")
        pk_specified = bool(pk)
        context["pk_specified"] = pk_specified

        chant = self.get_object()
        if chant.volpiano:
            has_syl_text = bool(chant.manuscript_syllabized_full_text)
            # Note: the second value returned is a flag indicating whether the alignment process
            # encountered errors. In future, this could be used to display a message to the user.
            text_and_mel, _ = align_text_and_volpiano(
                chant.get_best_text_for_syllabizing(),
                chant.volpiano,
                text_presyllabified=has_syl_text,
            )
            context["syllabized_text_with_melody"] = text_and_mel

        user = self.request.user
        context["user_can_proofread_chant"] = user_can_proofread_chant(user, chant)
        # in case the chant has no manuscript_full_text_std_spelling, we check Cantus Index
        # for the expected text for chants with the same Cantus ID, and pass it to the context
        # to suggest it to the user
        if not chant:
            return context
        cantus_id = chant.cantus_id
        if not cantus_id:
            return context
        if not chant.manuscript_full_text_std_spelling:
            suggested_fulltext = get_suggested_fulltext(chant.cantus_id)
            context["suggested_fulltext"] = suggested_fulltext
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
        # Take user back to the referring page
        # `ref` url parameter is used to indicate referring page
        next_url = self.request.GET.get("ref")
        if next_url:
            return self.request.POST.get("referrer")
        else:
            # ref not found, stay on the same page after save
            return self.request.get_full_path()


class ChantEditSyllabificationView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = "chant_syllabification_edit.html"
    model = Chant
    context_object_name = "chant"
    form_class = ChantEditSyllabificationForm
    pk_url_kwarg = "chant_id"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flattened_syls_text = ""

    def test_func(self):
        chant = self.get_object()
        source = chant.source
        user = self.request.user

        return user_can_edit_chants_in_source(user, source)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        chant = self.get_object()

        if chant.volpiano:
            # Second value returned is a flag indicating
            # whether the alignment process encountered errors.
            # In future, this could be used to display a message to the user.
            text_and_mel, _ = align_text_and_volpiano(
                chant_text=self.flattened_syls_text,
                volpiano=chant.volpiano,
                text_presyllabified=True,
            )
            context["syllabized_text_with_melody"] = text_and_mel

        return context

    def get_initial(self):
        initial = super().get_initial()
        chant = self.get_object()
        has_syl_text = bool(chant.manuscript_syllabized_full_text)
        syls_text = syllabify_text(
            text=chant.get_best_text_for_syllabizing(),
            clean_text=True,
            text_presyllabified=has_syl_text,
        )
        self.flattened_syls_text = flatten_syllabified_text(syls_text)
        initial["manuscript_syllabized_full_text"] = self.flattened_syls_text
        return initial

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
