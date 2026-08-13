import hashlib
import urllib.parse
from collections import Counter, defaultdict
from typing import Optional, Any, Iterator
import string

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.postgres.aggregates import ArrayAgg
from django.core.cache import cache
from django.db import transaction
from django.db.models import Case, F, Q, QuerySet, When
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
    View,
)
from volpiano_display_utilities.latin_word_syllabification import LatinError
from volpiano_display_utilities.cantus_text_syllabification import (
    syllabify_text,
    flatten_syllabified_text,
)
from volpiano_display_utilities.text_volpiano_alignment import align_text_and_volpiano

from cantusindex import (
    BaseChantText,
    CANTUS_ID_PATTERN,
    MAX_CANTUS_ID_LENGTH,
    ClusterElement,
    get_base_chant_text,
    get_cluster_elements,
    get_suggested_chants,
    get_suggested_fulltext,
    get_ci_text_search,
)
from main_app.forms import (
    ChantCreateForm,
    ChantEditForm,
    ChantEditSyllabificationForm,
    ChantSearchForm,
)
from main_app.models import (
    Chant,
    ChantElement,
    Feast,
    Genre,
    Segment,
    Source,
    Sequence,
    Service,
)
from main_app.permissions import CustomAccessMixin

from main_app.mixins import JSONResponseMixin
from users.models import User

ADVANCED_SEARCH_FIELDS: tuple[str, ...] = (
    # GET params belonging to the collapsible "Advanced search" section of
    # chant_search.html; used to auto-expand it when any of them are set.
    "service",
    "genre",
    "cantus_id",
    "mode",
    "position",
    "melodies",
    "feast",
    "liturgical_function",
    "segment",
    # "indexing_notes_op" is intentionally excluded: its <select> has no blank
    # option, so browsers always submit a value ("contains") even when the user
    # never touched it. Including it here would keep this section expanded on
    # every search.
    "indexing_notes",
)

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
    "source__shelfmark",
    "source__holding_institution__siglum",
    "source__holding_institution__name",
    "feast__id",
    "feast__description",
    "feast__name",
    "service__id",
    "service__description",
    "service__name",
    "genre__id",
    "genre__description",
    "genre__name",
)

ONLY_FIELDS = (
    "id",
    "genre",
    "feast",
    "service",
    "source",
    "source__holding_institution__siglum",
    "source__shelfmark",
    "source__holding_institution__city",
    "source__holding_institution__name",
    "source__name",
    "title",
    "incipit",
    "folio",
    "search_vector",
    "manuscript_full_text_std_spelling",
    "position",
    "image_link",
    "manuscript_full_text",
    "cantus_id",
    "mode",
    "volpiano",
    "feast__name",
    "feast__description",
)


def split_folio_name(folio: str) -> tuple[str, str, str]:
    """
    Splits a folio name into its parts: prefix, number, and suffix.

    If
    """
    prefix = folio[0] if folio[0].isalpha() else ""
    number = folio.strip(string.ascii_letters)
    suffix = folio[-1] if folio[-1].isalpha() else ""
    return prefix, number, suffix


def create_folio_ranges(folios: list[str]) -> str:
    """
    Combines a list of folios (in ascending order)
    into a single string with ranges.

    Example:
    combine_folio_names(['001r', '001v', '002r', '003r', '003v','005v'])
    returns '001r-002r, 003r-003v, 005v'

    Note: The resulting ranges may include folios that do not contain
    chants with the given feast *if* the feast is on unnumbered folios or
    adjacent to unnumbered folios. For example, if a feast appears on folios
    001v and 002r, but there is an unnumbered folio (per CantusDB convention,
    called 001w and 001x) between them, the resulting feast range will appear
    as '001v-002r'. Similarly, if the feast appears on 001v and 001x, the range
    will appear as '001v-001x'.
    """
    folio_ranges: list[dict[str, str]] = [{"start": folios[0]}]
    most_recent_folio = folios[0]
    most_recent_folio_split = split_folio_name(most_recent_folio)
    for curr_folio in folios[1:]:
        curr_folio_split = split_folio_name(curr_folio)
        # Check if the folio number has incremented by one.
        # We use this in the second conditional block below but
        # check it here to catch if the folio number is not coercible
        # to an integer.
        try:
            folio_num_inc_1 = (
                int(curr_folio_split[1]) == int(most_recent_folio_split[1]) + 1
            )
        except ValueError:
            folio_num_inc_1 = False
        # If the folio prefix has changed, start a new range
        if curr_folio_split[0] != most_recent_folio_split[0]:
            folio_ranges[-1]["end"] = most_recent_folio
            folio_ranges.append({"start": curr_folio})
        # Next, we add to the current range if one of the following conditions
        # is met:
        # 1. The folio number does not change.
        # 2. The folio number increases by one and either (a) there is no suffix
        #    or (b) the suffix of the current folio is "r" and the suffix of the previous
        #    folio was not "r".
        elif (curr_folio_split[1] == most_recent_folio_split[1]) or (
            folio_num_inc_1
            and (
                curr_folio_split[2] == ""
                or (curr_folio_split[2] == "r" and most_recent_folio_split[2] != "r")
            )
        ):
            folio_ranges[-1]["end"] = curr_folio
        else:
            folio_ranges[-1]["end"] = most_recent_folio
            folio_ranges.append({"start": curr_folio})
        most_recent_folio = curr_folio
        most_recent_folio_split = curr_folio_split
    folio_ranges[-1]["end"] = most_recent_folio
    # Create strings in the format "start-end" for each range.
    # If a folio range only contains one folio, we don't need to display the end folio.
    folio_range_strs = [
        (
            f"{folio_range['start']}-{folio_range['end']}"
            if folio_range["start"] != folio_range["end"]
            else f"{folio_range['start']}"
        )
        for folio_range in folio_ranges
    ]
    return ", ".join(folio_range_strs)


def get_feast_selector_options(source: Source) -> list[tuple[int, str, str]]:
    """
    Generate a list of feasts in the source to be used in the feast selector
    dropdown. Returns a list of tuples in the following format
    [
        (feast_id, feast_name, folios),
        (feast_id, feast_name, folios),
        ...
    ]
    where folios is a list of folio ranges associated with the feast.

    Args:
        source (Source object): The source for which the dropdown is created.

    Returns:
        list of tuples: A list of feasts and their associated folios.
    """
    chant_set_w_feasts: QuerySet[Chant, tuple[int, str]] = source.chant_set.exclude(
        feast=None
    ).values_list("feast_id", "feast__name")
    feasts_agg_folios: Iterator[tuple[int, str, list[str]]] = (
        chant_set_w_feasts.annotate(folios=ArrayAgg("folio", distinct=True))
        .order_by("folios")
        .iterator()
    )
    feasts_with_folio_range = []
    for feast_with_folio in feasts_agg_folios:
        feasts_with_folio_range.append(
            (
                feast_with_folio[0],
                feast_with_folio[1],
                create_folio_ranges(feast_with_folio[2]),
            )
        )
    return feasts_with_folio_range


def get_chants_with_feasts(
    chants_in_folio: QuerySet[Chant],
) -> list[tuple[Optional[Feast], list[Chant]]]:
    """
    Takes a queryset of chants and returns a list
    of tuples in the following format:
    [
      (feast_id_1, [chant, chant, ...]),
      (feast_id_2, [chant, chant, ...]),
      ...
    ].

    The queryset of chants should have the related feast object prefetched.
    """

    feasts_chants = defaultdict(list)
    for chant in chants_in_folio:
        # if feasts_chants is empty, append a new list
        if chant.feast:
            feasts_chants[chant.feast].append(chant)
        # else, append the following: ["no_feast", []]
        else:
            feasts_chants[None].append(chant)

    # # go through feasts_chants and replace feast_id with the corresponding Feast object
    out: list[tuple[Optional[Feast], list[Chant]]] = []
    for feast, chants in feasts_chants.items():
        out.append((feast, chants))
    return out


def get_chants_with_folios(chants_in_feast: QuerySet) -> list:
    # this will be a nested list of the following format:
    # [
    #   [folio_1, [chant, chant, ...]],
    #   [folio_2, [chant, chant, ...]],
    #   ...
    # ]
    folios_chants = defaultdict(list)
    for chant in chants_in_feast.order_by("folio"):
        # if folios_chants is empty, or if your current chant in the for loop
        # belongs in a different folio than the last chant,
        # append a new list with your current chant's folio
        if chant.folio:
            folios_chants[chant.folio].append(chant)

    # sort the chants associated with a particular folio by c_sequence
    for folio, chants in folios_chants.items():
        folios_chants[folio] = sorted(chants, key=lambda x: x.c_sequence)

    return list(folios_chants.items())


class ChantDetailView(CustomAccessMixin, JSONResponseMixin, DetailView):  # type: ignore[type-arg]
    """
    Displays a single Chant object. Accessed with ``chants/<int:pk>``
    """

    model = Chant
    context_object_name = "chant"
    template_name = "chant_detail.html"
    json_fields = [
        "id",
        "folio",
        "c_sequence",
        "cantus_id",
        "feast__name",
        "service__name",
        "service__description",
        "genre__name",
        "genre__description",
        "position",
        "mode",
        "differentia",
        "differentiae_database",
        "marginalia",
        "finalis",
        "manuscript_full_text",
        "manuscript_full_text_std_spelling",
        "volpiano",
        "source_id",
    ]

    def test_func(self) -> bool:
        chant_id = self.kwargs.get(self.pk_url_kwarg)
        chant = get_object_or_404(Chant, pk=chant_id)
        source = chant.source
        return (
            source.published
            or self.user_assigned_to_source(source)
            or self.user_is_global_viewer
        )

    def get_queryset(self) -> QuerySet[Chant]:
        qs = super().get_queryset()
        return qs.select_related(
            "source__holding_institution",
            "service",
            "genre",
            "feast",
            "project",
            "created_by",
            "last_updated_by",
        ).prefetch_related("source__segment_m2m", "source__notation")

    @staticmethod
    def _attributable_user(user: Optional[User]) -> Optional[User]:
        """Returns ``user``, or ``None`` if it's the generic admin account.

        Records migrated from OldCantus are attributed to a generic "Cantus
        Database Administrator" account (settings.GENERIC_ADMIN_FULL_NAME)
        rather than a named editor. Per Debra's feedback on #2104, this
        placeholder shouldn't be shown in the public attribution footer until
        a real editor is recorded.
        """
        if (
            user
            and (user.full_name or "").strip().lower()
            == settings.GENERIC_ADMIN_FULL_NAME
        ):
            return None
        return user

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        chant = context["chant"]
        source = chant.source

        context["user_can_edit_chant"] = self.user_assigned_to_source(source)
        context["attribution_created_by"] = self._attributable_user(chant.created_by)
        context["attribution_last_updated_by"] = self._attributable_user(
            chant.last_updated_by
        )
        context["bower_segment"] = (
            source is not None
            and source.segment_m2m.filter(id=settings.BOWER_SEGMENT_ID).exists()
        )
        context["source_notation"] = source.notation.first() if source else None

        language = chant.text_language
        if language and language.pk == 2:
            language_str = "kanienkeha"
        else:
            language_str = None

        # syllabification section
        if chant.volpiano:
            has_syl_text = bool(chant.manuscript_syllabized_full_text)
            try:
                text_and_mel, _ = align_text_and_volpiano(
                    chant.get_best_text_for_syllabizing(),
                    chant.volpiano,
                    text_presyllabified=has_syl_text,
                    language=language_str,
                )
            except LatinError:
                text_and_mel = None
            context["syllabized_text_with_melody"] = text_and_mel

        if project := chant.project:
            context["project"] = project.name

        # some chants don't have a source, for those chants, stop here without further calculating
        # other context variables
        if not chant.source:
            return context

        # source navigation section
        chants_in_source = chant.source.chant_set.select_related(
            "source__holding_institution", "feast", "genre", "service"
        )
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

        chants_current_folio = chants_in_source.filter(folio=chant.folio).order_by(
            "c_sequence"
        )
        context["exists_on_cantus_ultimus"] = source.exists_on_cantus_ultimus
        context["feasts_current_folio"] = get_chants_with_feasts(chants_current_folio)

        if context["previous_folio"]:
            chants_previous_folio = chants_in_source.filter(
                folio=context["previous_folio"]
            ).order_by("c_sequence")
            context["feasts_previous_folio"] = get_chants_with_feasts(
                chants_previous_folio
            )

        if context["next_folio"]:
            chants_next_folio = chants_in_source.filter(
                folio=context["next_folio"]
            ).order_by("c_sequence")
            context["feasts_next_folio"] = get_chants_with_feasts(chants_next_folio)

        return context


class ChantByCantusIDView(CustomAccessMixin, ListView):  # type: ignore[type-arg]
    # model = Chant
    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_seq_by_cantus_id.html"
    test_req = False

    def dispatch(self, request, *args, **kwargs):
        # decode cantus_id, which might contain forward slash and is thus percent-encoded
        self.cantus_id = urllib.parse.unquote(kwargs["cantus_id"])
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[Chant]:
        chant_set = Chant.objects.filter(cantus_id=self.cantus_id).select_related(
            "source__holding_institution", "service", "genre", "feast"
        )
        sequence_set = Sequence.objects.filter(cantus_id=self.cantus_id).select_related(
            "source__holding_institution", "service", "genre", "feast"
        )

        if not self.user.is_superuser and not self.user_is_global_viewer:
            chant_set = chant_set.filter(source__in=self.published_and_assigned_sources)
            sequence_set = sequence_set.filter(
                source__in=self.published_and_assigned_sources
            )
        # the union operation turns sequences into chants, the resulting queryset contains only
        # "chant" objects this forces us to do something special on the template to render correct
        # absolute url for sequences
        queryset = chant_set.union(sequence_set)
        queryset = queryset.order_by("source__holding_institution__siglum")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["cantus_id"] = self.cantus_id
        return context


class ChantSearchView(CustomAccessMixin, ListView):  # type: ignore[type-arg]
    """
    Searches Chants and displays them as a list, accessed with ``chant-search/``

    This view uses the same template as ``ChantSearchMSView``

    If no ``GET`` parameters, returns empty queryset

    ``GET`` parameters:
        ``service``: Filters by Service of Chant
        ``genre``: Filters by Genre of Chant
        ``cantus_id``: Filters by the Cantus ID field of Chant
        ``mode``: Filters by mode of Chant
        ``position``: Filters by position of chant
        ``melodies``: Filters Chant by whether or not it contains a melody in
                      Volpiano form. Valid values are "true" or "false".
        ``feast``: Filters by Feast of Chant
        ``liturgical_function``: Filters by liturgical function of Chant
        ``segment``: Filters by Segment of the Chant's Source
        ``keyword``: Searches text of Chant for keywords
        ``op``: Operation to take with keyword search. Options are "contains", "starts_with", and "ends_with"
        ``indexing_notes``: Searches indexing notes of Chant/Sequence for text
        ``indexing_notes_op``: Operation to take with indexing notes search. Options are "contains" and "starts_with"
    """

    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_search.html"
    test_req = False

    def get_context_data(self, **kwargs) -> dict:
        context = super().get_context_data(**kwargs)
        # Add to context a QuerySet of dicts with id and name of each Genre
        context["genres"] = Genre.objects.all().order_by("name").values("id", "name")
        context["services"] = (
            Service.objects.all().order_by("name").values("id", "name")
        )
        context["liturgical_functions"] = Chant.LITURGICAL_FUNCTION_CHOICES
        # "Benedicamus Domino" is a chant-level project designation, not a
        # source segment, so it's excluded here (see #2131). "Cantus Database"
        # is listed first (after "Any", added in the template), the rest
        # alphabetically.
        context["segments"] = list(
            Segment.objects.exclude(id=settings.BENEDICAMUS_DOMINO_SEGMENT_ID)
            .order_by(
                Case(When(id=settings.CANTUS_SEGMENT_ID, then=0), default=1),
                "name",
            )
            .values("id", "name")
        )
        context["advanced_search_active"] = any(
            self.request.GET.get(field) for field in ADVANCED_SEARCH_FIELDS
        )
        feast_param = self.request.GET.get("feast")
        context["search_form"] = ChantSearchForm(
            initial=(
                {"feast": feast_param} if feast_param and feast_param.isdigit() else {}
            )
        )
        context["query_empty"] = False if self.request.GET else True
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
        search_service: Optional[str] = self.request.GET.get("service")
        if search_service:
            search_parameters.append(f"service={search_service}")
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
        search_liturgical_function: Optional[str] = self.request.GET.get(
            "liturgical_function"
        )
        if search_liturgical_function:
            search_parameters.append(
                f"liturgical_function={search_liturgical_function}"
            )
        search_bar: Optional[str] = self.request.GET.get("search_bar")
        if search_bar:
            search_parameters.append(f"search_bar={search_bar}")
        search_segment: Optional[str] = self.request.GET.get("segment")
        if search_segment:
            search_parameters.append(f"segment={search_segment}")
        search_indexing_notes_op: Optional[str] = self.request.GET.get(
            "indexing_notes_op"
        )
        if search_indexing_notes_op:
            search_parameters.append(f"indexing_notes_op={search_indexing_notes_op}")
        search_indexing_notes: Optional[str] = self.request.GET.get("indexing_notes")
        if search_indexing_notes:
            search_parameters.append(f"indexing_notes={search_indexing_notes}")

        url_with_search_params: str = current_url + "?"
        if search_parameters:
            joined_search_parameters: str = "&".join(search_parameters)
            url_with_search_params += joined_search_parameters

        context["url_with_search_params"] = url_with_search_params

        return context

    def get_segment_id(self) -> Optional[str]:
        return self.request.GET.get("segment")

    def get_queryset(self) -> QuerySet[Chant]:
        # if user has just arrived on the Chant Search page, there will be no GET parameters.
        if not self.request.GET:
            return Chant.objects.none()

        # Create a Q object to filter the QuerySet of Chants
        q_obj_filter = Q()

        # if the search is accessed by the global search bar
        if search_bar := self.request.GET.get("search_bar"):
            chant_set = Chant.objects.select_related(
                "source__holding_institution", "feast", "service", "genre"
            )
            sequence_set = Sequence.objects.select_related(
                "source__holding_institution", "feast", "service", "genre"
            )

            search_bar_term_contains_digits = any(map(str.isdigit, search_bar))
            if search_bar_term_contains_digits:
                # if search bar is doing Cantus ID search
                q_obj_filter &= Q(cantus_id__icontains=search_bar)
                chant_set = chant_set.filter(q_obj_filter).only(*ONLY_FIELDS)
                sequence_set = sequence_set.filter(q_obj_filter).only(*ONLY_FIELDS)
            else:
                # if search bar is doing incipit search
                search_term = search_bar
                ms_spelling_filter = Q(manuscript_full_text__istartswith=search_term)
                std_spelling_filter = Q(
                    manuscript_full_text_std_spelling__istartswith=search_term
                )
                incipit_filter = Q(incipit__istartswith=search_term)
                search_term_filter = (
                    ms_spelling_filter | std_spelling_filter | incipit_filter
                )
                chant_set = chant_set.filter(search_term_filter).only(*ONLY_FIELDS)
                sequence_set = sequence_set.filter(search_term_filter).only(
                    *ONLY_FIELDS
                )
            if not self.user.is_superuser and not self.user_is_global_viewer:
                chant_set = chant_set.filter(
                    source__in=self.published_and_assigned_sources
                )
                sequence_set = sequence_set.filter(
                    source__in=self.published_and_assigned_sources
                )
            if segment_id := self.get_segment_id():
                chant_set = chant_set.filter(source__segment_m2m=segment_id)
                sequence_set = sequence_set.filter(source__segment_m2m=segment_id)

            queryset = chant_set.union(sequence_set, all=True)
        else:
            # The field names should be keys in the "GET" QueryDict if the search button has been
            # clicked, even if the user put nothing into the search form and hit "apply" immediately.
            # In that case, we return all chants + seqs filtered by the search form.
            if service_id := self.request.GET.get("service"):
                q_obj_filter &= Q(service__id=service_id)

            if genre_id := self.request.GET.get("genre"):
                q_obj_filter &= Q(genre__id=int(genre_id))

            if cantus_id := self.request.GET.get("cantus_id"):
                q_obj_filter &= Q(cantus_id__icontains=cantus_id)

            if mode := self.request.GET.get("mode"):
                q_obj_filter &= Q(mode=mode)

            if position := self.request.GET.get("position"):
                q_obj_filter &= Q(position=position)

            if melodies := self.request.GET.get("melodies"):
                if melodies == "true":
                    q_obj_filter &= Q(volpiano__isnull=False)

            if feast_id := self.request.GET.get("feast"):
                if feast_id.isdigit():
                    q_obj_filter &= Q(feast_id=feast_id)

            if liturgical_function := self.request.GET.get("liturgical_function"):
                q_obj_filter &= Q(liturgical_function=liturgical_function)

            # Filter the QuerySet with Q object
            chant_set = Chant.objects.filter(q_obj_filter).select_related(
                "source__holding_institution", "feast", "service", "genre"
            )
            sequence_set = Sequence.objects.filter(q_obj_filter).select_related(
                "source__holding_institution", "feast", "service", "genre"
            )

            # Filter the QuerySet based on permissions
            if not self.user.is_superuser and not self.user_is_global_viewer:
                chant_set = chant_set.filter(
                    source__in=self.published_and_assigned_sources
                )
                sequence_set = sequence_set.filter(
                    source__in=self.published_and_assigned_sources
                )

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
                elif operation and operation == "ends_with":
                    ms_spelling_filter = Q(manuscript_full_text__iendswith=keyword)
                    std_spelling_filter = Q(
                        manuscript_full_text_std_spelling__iendswith=keyword
                    )
                    incipit_filter = Q(incipit__iendswith=keyword)
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

            if notes := self.request.GET.get("indexing_notes"):
                operation = self.request.GET.get("indexing_notes_op")
                # the operation parameter can be "contains" or "starts_with"
                if operation == "contains":
                    indexing_notes_filter = Q(indexing_notes__icontains=notes)
                else:
                    indexing_notes_filter = Q(indexing_notes__istartswith=notes)
                chant_set = chant_set.filter(indexing_notes_filter)
                sequence_set = sequence_set.filter(indexing_notes_filter)

            # Fetch only the values necessary for rendering the template
            chant_set = chant_set.only(*ONLY_FIELDS)
            sequence_set = sequence_set.only(*ONLY_FIELDS)

            if segment_id := self.get_segment_id():
                chant_set = chant_set.filter(source__segment_m2m=segment_id)
                sequence_set = sequence_set.filter(source__segment_m2m=segment_id)

            # once unioned, the queryset cannot be filtered/annotated anymore, so we put union to the last
            queryset = chant_set.union(sequence_set, all=True)

        # Apply sorting
        order_get_param: Optional[str] = self.request.GET.get("order")
        sort_get_param: Optional[str] = self.request.GET.get("sort")

        order_field_mapping = {
            "feast": "feast__name",
            "service": "service__name",
            "genre": "genre__name",
            "has_fulltext": "manuscript_full_text",
            "has_melody": "volpiano",
            "has_image": "image_link",
            "incipit": "incipit",
            "cantus_id": "cantus_id",
            "mode": "mode",
        }

        order = order_field_mapping.get(
            order_get_param, "source__holding_institution__siglum"
        )

        # Reverse logic for 'has_' fields: we want entries WITH data first when sorting ASC
        reverse_sort = order_get_param in ["has_fulltext", "has_melody", "has_image"]

        # Determine sort direction, flipping if it's a 'has_' field
        if sort_get_param == "desc":
            order_expression = (
                F(order).asc(nulls_last=True)
                if reverse_sort
                else F(order).desc(nulls_last=True)
            )
        else:
            order_expression = (
                F(order).desc(nulls_last=True)
                if reverse_sort
                else F(order).asc(nulls_last=True)
            )

        return queryset.order_by(order_expression, "id")


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
            context["source"] = Source.objects.select_related(
                "holding_institution"
            ).get(id=self.request.GET.get("source"))
        return context


class ChantSearchMSView(CustomAccessMixin, ListView):  # type: ignore[type-arg]
    """
    Searches chants/sequences in a certain manuscript, accessed with
    ``chant-search-ms/<int:source_pk>``

    This view uses the same template as ``ChantSearchView``

    If no ``GET`` parameters, returns empty queryset

    ``GET`` parameters:
        ``service``: Filters by the service/mass of Chant
        ``genre``: Filters by Genre of Chant
        ``cantus_id``: Filters by the Cantus ID field of Chant
        ``mode``: Filters by mode of Chant
        ``melodies``: Filters Chant by whether or not it contains a melody in
                      Volpiano form. Valid values are "true" or "false".
        ``feast``: Filters by Feast of Chant
        ``liturgical_function``: Filters by liturgical function of Chant
        ``keyword``: Searches text of Chant for keywords
        ``op``: Operation to take with keyword search. Options are "contains", "starts_with", and "ends_with"
        ``indexing_notes``: Searches indexing notes of Chant/Sequence for text
        ``indexing_notes_op``: Operation to take with indexing notes search. Options are "contains" and "starts_with"
    """

    paginate_by = 100
    context_object_name = "chants"
    template_name = "chant_search.html"
    source: Source

    def test_func(self) -> bool:
        source_id = self.kwargs.get("source_pk")
        self.source = get_object_or_404(Source, pk=source_id)
        return (
            self.source.published
            or self.user_assigned_to_source(self.source)
            or self.user_is_global_viewer
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["source"] = self.source
        # Add to context a QuerySet of dicts with id and name of each Genre
        context["genres"] = Genre.objects.all().order_by("name").values("id", "name")
        context["services"] = (
            Service.objects.all().order_by("name").values("id", "name")
        )
        context["liturgical_functions"] = Chant.LITURGICAL_FUNCTION_CHOICES
        context["advanced_search_active"] = any(
            self.request.GET.get(field) for field in ADVANCED_SEARCH_FIELDS
        )
        feast_param = self.request.GET.get("feast")
        context["search_form"] = ChantSearchForm(
            initial=(
                {"feast": feast_param} if feast_param and feast_param.isdigit() else {}
            )
        )
        context["order"] = self.request.GET.get("order")
        context["sort"] = self.request.GET.get("sort")
        # This is searching in a specific source, pass the source into context

        current_url = self.request.path
        search_parameters = []

        search_op = self.request.GET.get("op")
        if search_op:
            search_parameters.append(f"op={search_op}")
        search_keyword = self.request.GET.get("keyword")
        if search_keyword:
            search_parameters.append(f"keyword={search_keyword}")
        search_service = self.request.GET.get("service")
        if search_service:
            search_parameters.append(f"service={search_service}")
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
        search_liturgical_function = self.request.GET.get("liturgical_function")
        if search_liturgical_function:
            search_parameters.append(
                f"liturgical_function={search_liturgical_function}"
            )
        search_indexing_notes_op = self.request.GET.get("indexing_notes_op")
        if search_indexing_notes_op:
            search_parameters.append(f"indexing_notes_op={search_indexing_notes_op}")
        search_indexing_notes = self.request.GET.get("indexing_notes")
        if search_indexing_notes:
            search_parameters.append(f"indexing_notes={search_indexing_notes}")

        if search_parameters:
            joined_search_parameters = "&".join(search_parameters)
            url_with_search_params = current_url + "?" + joined_search_parameters
        else:
            url_with_search_params = current_url + "?"

        context["url_with_search_params"] = url_with_search_params
        return context

    def get_queryset(self) -> QuerySet[Chant]:
        # If the "apply" button hasn't been clicked, return empty queryset
        if not self.request.GET:
            return Chant.objects.none()
        # Source 680970 (MS 73) melody search was blocked in #1635; re-enabled in #1893.

        # Create a Q object to filter the QuerySet of Chants
        q_obj_filter = Q()
        # For every GET parameter other than incipit, add to the Q object
        if service_id := self.request.GET.get("service"):
            q_obj_filter &= Q(service__id=service_id)

        if genre_id := self.request.GET.get("genre"):
            q_obj_filter &= Q(genre__id=int(genre_id))

        if cantus_id := self.request.GET.get("cantus_id"):
            q_obj_filter &= Q(cantus_id__icontains=cantus_id)

        if mode := self.request.GET.get("mode"):
            q_obj_filter &= Q(mode=mode)

        if melodies := self.request.GET.get("melodies"):
            if melodies == "true":
                q_obj_filter &= Q(volpiano__isnull=False)
            if melodies == "false":
                q_obj_filter &= Q(volpiano__isnull=True)
        if feast_id := self.request.GET.get("feast"):
            if feast_id.isdigit():
                q_obj_filter &= Q(feast_id=feast_id)

        if liturgical_function := self.request.GET.get("liturgical_function"):
            q_obj_filter &= Q(liturgical_function=liturgical_function)

        order_value = self.request.GET.get("order")
        sort_get_param: Optional[str] = self.request.GET.get("sort")

        order_field_mapping = {
            "feast": "feast__name",
            "service": "service__name",
            "genre": "genre__name",
            "has_fulltext": "manuscript_full_text",
            "has_melody": "volpiano",
            "has_image": "image_link",
            "incipit": "incipit",
            "cantus_id": "cantus_id",
            "mode": "mode",
        }

        order = order_field_mapping.get(
            order_value, "source__holding_institution__siglum"
        )

        # Reverse logic for 'has_' fields: we want entries WITH data first when sorting ASC
        reverse_sort = order_value in ["has_fulltext", "has_melody", "has_image"]

        # Determine sort direction, flipping if it's a 'has_' field
        if sort_get_param == "desc":
            order_expression = (
                F(order).asc(nulls_last=True)
                if reverse_sort
                else F(order).desc(nulls_last=True)
            )
        else:
            order_expression = (
                F(order).desc(nulls_last=True)
                if reverse_sort
                else F(order).asc(nulls_last=True)
            )

        source_id = self.kwargs["source_pk"]
        source = Source.objects.get(id=source_id)
        queryset = (
            source.sequence_set
            if 4064 in source.segment_m2m.values_list("id", flat=True)
            else source.chant_set
        )

        # Filter the QuerySet with Q object
        queryset = queryset.select_related(
            "source__holding_institution", "feast", "service", "genre"
        ).filter(q_obj_filter)
        # Fetch only the values necessary for rendering the template
        queryset = queryset.only(*ONLY_FIELDS)
        # Finally, do keyword searching over the QuerySet
        if keyword := self.request.GET.get("keyword"):
            operation = self.request.GET.get("op")
            # the operation parameter can be "contains", "starts_with", or "ends_with"
            if operation == "contains":
                ms_spelling_filter = Q(manuscript_full_text__icontains=keyword)
                std_spelling_filter = Q(
                    manuscript_full_text_std_spelling__icontains=keyword
                )
                incipit_filter = Q(incipit__icontains=keyword)
            elif operation == "ends_with":
                ms_spelling_filter = Q(manuscript_full_text__iendswith=keyword)
                std_spelling_filter = Q(
                    manuscript_full_text_std_spelling__iendswith=keyword
                )
                incipit_filter = Q(incipit__iendswith=keyword)
            else:
                ms_spelling_filter = Q(manuscript_full_text__istartswith=keyword)
                std_spelling_filter = Q(
                    manuscript_full_text_std_spelling__istartswith=keyword
                )
                incipit_filter = Q(incipit__istartswith=keyword)

            keyword_filter = ms_spelling_filter | std_spelling_filter | incipit_filter
            queryset = queryset.filter(keyword_filter)
        if notes := self.request.GET.get("indexing_notes"):
            operation = self.request.GET.get("indexing_notes_op")
            # the operation parameter can be "contains" or "starts_with"
            if operation == "contains":
                indexing_notes_filter = Q(indexing_notes__icontains=notes)
            else:
                indexing_notes_filter = Q(indexing_notes__istartswith=notes)
            queryset = queryset.filter(indexing_notes_filter)
        # ordering with the folio string gives wrong order
        # old cantus is also not strictly ordered by folio (there are outliers)
        # so we order by id for now, which is the order that the chants are entered into the DB
        queryset = queryset.order_by(order_expression, "id")
        return queryset


class ChantCreateView(CustomAccessMixin, CreateView):  # type: ignore[type-arg]
    """Create chants in a certain manuscript, accessed with `chant-create/<int:source_pk>`.

    This view displays the chant input form and provide access to
    "input tool" and "chant suggestion tool" to facilitate the input process.
    """

    model = Chant
    template_name = "chant_create.html"
    form_class = ChantCreateForm
    pk_url_kwarg = "source_pk"
    source: Source
    latest_chant: Optional[Chant]

    def test_func(self) -> bool:
        source_id = self.kwargs.get(self.pk_url_kwarg)
        self.source = get_object_or_404(Source, id=source_id)
        return self.user_assigned_to_source(self.source)

    def get_success_url(self):
        """
        Get the incipit of the created chant (generated by a signal)
        and display a success message.
        """
        self.object.refresh_from_db()
        messages.success(
            self.request,
            "Chant '" + self.object.incipit + "' created successfully!",
        )
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
            self.latest_chant = latest_chant
        except Chant.DoesNotExist:
            # if there is no chant in source, start with folio 001r, and c_sequence 1
            self.latest_chant = None
            return {
                "folio": "001r",
                "feast": "",
                "c_sequence": 1,
                "image_link": "",
            }
        latest_folio = latest_chant.folio if latest_chant.folio else "001r"
        latest_feast = latest_chant.feast.id if latest_chant.feast else ""
        latest_service = latest_chant.service.id if latest_chant.service else ""
        latest_seq = (
            latest_chant.c_sequence if latest_chant.c_sequence is not None else 0
        )
        latest_image = latest_chant.image_link if latest_chant.image_link else ""
        return {
            "folio": latest_folio,
            "feast": latest_feast,
            "service": latest_service,
            "c_sequence": latest_seq + 1,
            "image_link": latest_image,
        }

    def get_suggested_feasts(self, latest_chant: Chant) -> dict[Feast, int]:
        """based on the feast of the most recently edited chant, provide a
        list of suggested feasts that might follow the feast of that chant.

        Returns: a dictionary, with feast objects as keys and counts as values
        """
        current_feast = latest_chant.feast
        chants_that_end_current_feast = Chant.objects.filter(
            is_last_chant_in_feast=True, feast=current_feast
        ).select_related("next_chant__feast", "feast", "genre", "service")
        next_chants = [chant.next_chant for chant in chants_that_end_current_feast]
        next_feasts = [
            chant.feast
            for chant in next_chants
            if isinstance(chant, Chant)  # .get_next_chant() sometimes returns None
            and chant.feast is not None  # some chants aren't associated with a feast
        ]
        feast_counts = Counter(next_feasts)
        sorted_feast_counts = dict(
            sorted(feast_counts.items(), key=lambda item: item[1], reverse=True)
        )
        return sorted_feast_counts

    def get_context_data(self, **kwargs: Any) -> dict[Any, Any]:
        context = super().get_context_data(**kwargs)
        context["source"] = self.source
        previous_chant = self.latest_chant
        context["previous_chant"] = previous_chant
        suggested_feasts = None
        suggested_chants = None
        if previous_chant:
            suggested_feasts = self.get_suggested_feasts(previous_chant)
            previous_cantus_id = previous_chant.cantus_id
            if previous_cantus_id:
                suggested_chants = get_suggested_chants(previous_cantus_id)
        context["suggested_feasts"] = suggested_feasts
        context["suggested_chants"] = suggested_chants
        return context

    def get_form_kwargs(self):
        """
        In the case of a submitted form (there is data in the request),
        we copy the data dictionary and add the source id to it.
        """
        kwargs = super().get_form_kwargs()
        if "data" in kwargs:
            kwargs["data"] = kwargs["data"].copy()
            kwargs["data"]["source"] = self.source.id
        return kwargs

    def form_valid(self, form):
        """
        Adds the "created_by" and "updated_by" fields to the chant, then persists any
        composed cluster elements (troped chants) as ChantElement rows.

        The chant and its elements are saved in one transaction so a failure partway
        through element creation can't leave a chant with a half-built cluster.
        """
        form.instance.created_by = self.request.user
        form.instance.last_updated_by = self.request.user
        with transaction.atomic():
            response = super().form_valid(form)  # saves the chant → self.object
            self._create_elements(form.cleaned_data.get("elements_json") or [])
        return response

    def _create_elements(self, elements: list[dict[str, Any]]) -> None:
        """Persist a newly-created troped chant's composed elements as ChantElement rows.

        Per-instance ``save()`` (not ``bulk_create``) so django-reversion's post_save
        signal captures each element under the request's revision. Core elements get a
        blank ``cantus_id`` here regardless of what the client sent — the model invariant
        is that a core resolves its ID through the parent chant.
        """
        for order, element in enumerate(elements):
            is_core = element["kind"] == ChantElement.Kind.CORE
            ChantElement(
                chant=self.object,
                order=order,
                kind=element["kind"],
                text=element["text"],
                cantus_id=None if is_core else (element["cantus_id"] or None),
                proposed=element["proposed"],
            ).save()


class ChantDeleteView(CustomAccessMixin, DeleteView):  # type: ignore[type-arg]
    """
    The view for deleting a chant object

    This view is used in the chant-edit page, where an authorized user is allowed to
    edit or delete chants in a certain source.
    """

    model = Chant
    template_name = "chant_delete.html"
    object: Chant  # type hint to avoid typing error

    def test_func(self) -> bool:
        chant_id = self.kwargs.get(self.pk_url_kwarg)
        chant = get_object_or_404(Chant, id=chant_id)
        source = chant.source
        return self.user_assigned_to_source(source)

    def get_success_url(self):
        return reverse("source-edit-chants", args=[self.object.source.id])


class CISearchView(TemplateView):
    """
    Search in CI and write results in get_context_data
    Shown on the chant create page as the "Input Tool"
    """

    template_name = "ci_search.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["genres"] = list(
            Genre.objects.all().order_by("name").values("id", "name")
        )
        search_term: str = kwargs["search_term"]
        search_term: str = search_term.replace(" ", "+")  # for multiple keywords

        text_search_results: Optional[list[Optional[dict]]] = get_ci_text_search(
            search_term
        )

        # None means any CI request/response failure; an empty list means CI returned no matches
        context["ci_error"] = text_search_results is None

        cantus_id = []
        genre = []
        full_text = []

        if text_search_results:
            for result in text_search_results:
                if result:
                    cantus_id.append(result.get("cid", None))
                    genre.append(result.get("genre", None))
                    full_text.append(result.get("fulltext", None))

        context["results"] = list(zip(cantus_id, genre, full_text))
        return context


class CIComponentSearchView(LoginRequiredMixin, View):
    """
    Read-only JSON proxy for Cantus Index's text search (/json-text), backing the
    chant cluster prototype's inline component-element typeahead on the Create Chant
    page (issues #2128 / #2129). The browser can't call cantusindex.org directly
    (CORS), so we proxy it — the same mechanism as the "Input Tool" (CISearchView),
    but returning JSON for a live, as-you-type dropdown instead of a rendered popup.

    Results are cached briefly: CI's data changes rarely, so this spares repeat
    lookups and shields the typeahead from CI latency/outages. The cache key is the
    search term alone (not cluster-specific); ranking a cluster's own sub-IDs to the
    top is left to the client, which knows the active cluster.

    Matches are restricted to the genres that can actually be interleaved into a
    cluster (28 Jul 2026 demo feedback) — a whole antiphon or responsory is never a
    component element, and leaving them in buried the usable matches. Filtering here
    rather than in the browser keeps the cached payload small and the client dumb.

    This and its two sibling proxies (``CIBaseTextView``, ``CIClusterElementsView``)
    gate on ``LoginRequiredMixin`` alone — deliberately looser than the Create Chant
    page's ``CustomAccessMixin`` — because they only re-serve Cantus Index's public
    catalogue and hold no per-source data to guard.
    """

    MIN_QUERY_LENGTH: int = 3
    CACHE_TTL: int = 60 * 60  # seconds; CI text data is effectively static
    # Trope elements, hymn verses and litany verses — the genres a component element
    # can have. Tropes are the "Tp" family rather than a single code: a Sanctus trope's
    # elements are catalogued under the troped-chant genre (g04828:01 is TpSa, not Tp),
    # so match the whole prefix. "Psl" (prosula) is included because Cantus Index
    # defines it as a type of trope.
    #
    # Open question from the demo, deliberately not settled here: whether to constrain
    # on the genre CI reports (what this does) or on what the Cantus ID itself implies.
    COMPONENT_GENRE_PREFIX: str = "Tp"
    COMPONENT_GENRES: frozenset[str] = frozenset({"Psl", "HV", "LiV"})
    # How many matches the dropdown renders. The response reports the unclipped total so
    # the UI can say how many more there are instead of silently truncating.
    MAX_RESULTS: int = 25
    # Cantus Index's /json-text returns at most 100 matches for any term (verified
    # 2026-08 against several broad queries). Hitting that ceiling means the match set
    # was truncated upstream, before our genre filter ever saw it — so there may be
    # component elements we never had the chance to offer. That is a different claim
    # from "more matches than fit in the dropdown", and the UI words it differently.
    CI_RESULT_CAP: int = 100

    @classmethod
    def is_component_genre(cls, genre: Optional[str]) -> bool:
        """Whether a Cantus Index genre code can appear as a component element."""
        if not genre:
            return False
        code: str = genre.strip()
        return (
            code.startswith(cls.COMPONENT_GENRE_PREFIX) or code in cls.COMPONENT_GENRES
        )

    def get(self, request: HttpRequest, search_term: str) -> JsonResponse:
        """Return Cantus Index text-search matches for ``search_term`` as JSON."""
        # Unlike the ID views, `search_term` isn't pattern-guarded: it is a text query,
        # not an id, and it only ever lands in CI's /json-text/ path segment — never in a
        # host, a further sub-request, or anything reused to reshape a request — so the
        # `str` URL converter (which already excludes "/") is guard enough.
        term: str = search_term.strip()
        if len(term) < self.MIN_QUERY_LENGTH:
            return JsonResponse({"results": [], "total": 0, "capped": False})

        # Hash the term: free text may contain spaces/punctuation that are invalid
        # in a memcached key. (md5 is a key digest here, not a security primitive.)
        digest: str = hashlib.md5(
            term.lower().encode("utf-8"), usedforsecurity=False
        ).hexdigest()
        cache_key: str = f"ci-component-search:{digest}"
        cached: Optional[dict[str, Any]] = cache.get(cache_key)
        if cached is None:
            raw = get_ci_text_search(term.replace(" ", "+"))
            if raw is None:
                # None is a CI failure (timeout/non-200); flag it so the UI can show
                # an error state rather than a misleading "no matches". Not cached.
                return JsonResponse(
                    {"results": [], "total": 0, "capped": False, "error": True}
                )
            cached = {
                "results": [
                    {
                        "cid": result.get("cid"),
                        "genre": result.get("genre"),
                        "fulltext": result.get("fulltext"),
                    }
                    for result in raw
                    if result
                    and result.get("cid")
                    and self.is_component_genre(result.get("genre"))
                ],
                # Measured on CI's raw response, before genre filtering: the ceiling was
                # hit upstream, so matches were lost regardless of how few survive here.
                "capped": len(raw) >= self.CI_RESULT_CAP,
            }
            cache.set(cache_key, cached, self.CACHE_TTL)

        results: list[dict[str, Optional[str]]] = cached["results"]
        # `total` counts every match that survived filtering; `results` is the clipped
        # page the dropdown renders; `capped` says CI truncated the set before we saw it.
        return JsonResponse(
            {
                "results": results[: self.MAX_RESULTS],
                "total": len(results),
                "capped": cached["capped"],
            }
        )


class CIBaseTextView(LoginRequiredMixin, View):
    """
    Read-only JSON proxy for the standard full text to compose a chant's cores from
    (Cantus Index /json-cid/{cantus_id}), backing the Create Chant cluster composer
    (issues #2128 / #2129 / #2189). Sibling to ``CIComponentSearchView``: the browser
    can't reach cantusindex.org directly (CORS), so we proxy it, and cache briefly
    since CI text is effectively static.

    For a troped chant this is not that chant's own text but its **base chant's** —
    see ``get_base_chant_text`` for why, and for what CI is asked in order to find it.
    The response therefore reports the Cantus ID the text came from alongside the text,
    since it may not be the one that was asked for. Nothing displays it today — the
    composer seeds silently — but it is the only signal that the text was redirected.
    Note the request is still made by the *troped* ID: that is what the element bank
    probes for components (``g01349.tp14:01``, which hang off the troped chant, not the
    base), so the Cantus ID field must keep holding it.

    CI does not (yet) split a chant's text into elements, so the text arrives as one
    blob; the cataloguer splits it into cores, by hand or with the automatic split. An
    empty result is a normal outcome (unknown ID, or CI has no text) — the composer then
    lets the cataloguer type the text in. Empty/failed fetches are not cached, so a
    retry re-hits CI.
    """

    CACHE_TTL: int = 60 * 60  # seconds; CI text data is effectively static

    def get(self, request: HttpRequest, cantus_id: str) -> JsonResponse:
        """Return the text to seed ``cantus_id``'s cores from, and the ID it came from."""
        cid: str = cantus_id.strip()
        # CANTUS_ID_PATTERN rejects anything but a bare id, so a crafted value can't
        # append a query or fragment to the CI request path. The length bound keeps an
        # over-long id out of the cache key below.
        if (
            not cid
            or len(cid) > MAX_CANTUS_ID_LENGTH
            or not CANTUS_ID_PATTERN.fullmatch(cid)
        ):
            return JsonResponse({"base_text": "", "cantus_id": ""})

        # Keyed on the requested ID, and versioned because #2189 changed what is stored
        # here from a bare string to the resolved {cantus_id, text} pair.
        cache_key: str = f"ci-base-text:v2:{cid}"
        resolved: Optional[BaseChantText] = cache.get(cache_key)
        if resolved is None:
            resolved = get_base_chant_text(cid)
            if resolved["text"]:
                cache.set(cache_key, resolved, self.CACHE_TTL)

        return JsonResponse(
            {
                "base_text": resolved["text"] or "",
                "cantus_id": resolved["cantus_id"],
            }
        )


class CIClusterElementsView(LoginRequiredMixin, View):
    """
    Read-only JSON list of the trope elements Cantus Index already holds for a Cantus
    ID, backing the composer's element bank (28 Jul 2026 demo feedback on #2129): the
    cataloguer drags a chant's own catalogued elements straight in rather than
    text-searching for each one.

    Assembling the list costs several upstream requests (see ``get_cluster_elements``
    for why CI leaves no cheaper option), so the result is cached for an hour —
    including the empty result, which is the common case. Most chants are not troped,
    and without caching those would re-probe CI on every activation.

    An outage is *not* cached, though: ``get_cluster_elements`` returns None (rather than
    an empty list) when it couldn't reach CI, so a blip during the first load of a troped
    chant doesn't pin an empty bank for the whole hour — the next activation retries.
    """

    CACHE_TTL: int = (
        60 * 60
    )  # seconds; CI's catalogue of elements is effectively static

    def get(self, request: HttpRequest, cantus_id: str) -> JsonResponse:
        """Return the catalogued sub-elements of ``cantus_id`` as JSON."""
        cid: str = cantus_id.strip()
        if (
            not cid
            or len(cid) > MAX_CANTUS_ID_LENGTH
            or not CANTUS_ID_PATTERN.fullmatch(cid)
        ):
            return JsonResponse({"elements": []})

        cache_key: str = f"ci-cluster-elements:{cid}"
        elements: Optional[list[ClusterElement]] = cache.get(cache_key)
        if elements is None:
            fetched = get_cluster_elements(cid)
            # None means CI was unreachable, which is indistinguishable at CI's API from
            # a real "no elements" — cache the genuine empty list, never the outage.
            elements = fetched if fetched is not None else []
            if fetched is not None:
                cache.set(cache_key, elements, self.CACHE_TTL)

        return JsonResponse({"elements": elements})


class SourceEditChantsView(CustomAccessMixin, UpdateView):  # type: ignore[type-arg]
    template_name = "chant_edit.html"
    model = Chant
    form_class = ChantEditForm
    pk_url_kwarg = "source_id"
    source: Source
    source_has_chants: bool

    def test_func(self) -> bool:
        source_id = self.kwargs.get(self.pk_url_kwarg)
        self.source = get_object_or_404(Source, id=source_id)
        return self.user_assigned_to_source(self.source)

    def get_queryset(self) -> QuerySet[Chant]:
        """
        Returns:
            a QuerySet of Chants in the Source, with associated feast,
            genre, and service objects selected.
        """
        source = self.source

        # get all chants in the specified source
        chants = source.chant_set.select_related("feast", "service", "genre")
        self.queryset = chants
        return self.queryset

    def get_object(self, queryset=None) -> Optional[Chant]:
        """
        Returns:
            the Chant that we wish to edit (specified by the Chant's pk).
            If no pk is specified or if no chants exist in the source,
            None is returned.
        """
        queryset = self.get_queryset()

        if self.request.method == "GET":
            pk = self.request.GET.get("pk")
        elif self.request.method == "POST":
            pk = self.request.POST.get("pk")
        else:
            pk = None

        self.source_has_chants = queryset.exists()
        if not pk:
            return None
        if not self.source_has_chants:
            return None
        return queryset.get(pk=pk)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source"] = self.source

        chants_in_source = self.queryset
        context["source_has_chants"] = self.source_has_chants
        if not context["source_has_chants"]:
            return context

        # generate options for the selectors on the right side of the page
        folios = (
            chants_in_source.values_list("folio", flat=True)
            .distinct()
            .order_by("folio")
        )
        context["folios"] = folios
        context["feast_selector_options"] = get_feast_selector_options(self.source)

        # generate the list of chants to display in the lower right sidebar card
        # this card displays chants in the source filtered by the folio or feast selector
        # if no feast or folio is selected, defaults to the chants on the first folio
        if feast_param := self.request.GET.get("feast"):
            # if there is a "feast" query parameter, it means the user has chosen a specific feast
            # need to render a list of chants, grouped and ordered by folio and within each group,
            # ordered by c_sequence. We get a Feast object in order to display some additional
            # feast information in that list of chants.
            context["feast"] = Feast.objects.get(id=feast_param)
            context["folios_current_feast"] = get_chants_with_folios(
                self.queryset.filter(feast_id=feast_param)
            )
        else:
            folio = self.request.GET.get("folio") or folios[0]
            context["folio_query"] = folio
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
            context["feasts_current_folio"] = get_chants_with_feasts(
                self.queryset.filter(folio=folio).order_by("c_sequence")
            )

        chant = self.object
        if not chant:
            return context
        if chant.volpiano:
            language = chant.text_language
            if language and language.pk == 2:
                language_str = "kanienkeha"
            else:
                language_str = None
            has_syl_text = bool(chant.manuscript_syllabized_full_text)
            # Note: the second value returned is a flag indicating whether the alignment process
            # encountered errors. In future, this could be used to display a message to the user.
            try:
                text_and_mel, _ = align_text_and_volpiano(
                    chant.get_best_text_for_syllabizing(),
                    chant.volpiano,
                    text_presyllabified=has_syl_text,
                    language=language_str,
                )
            except LatinError as err:
                messages.error(
                    self.request,
                    "Error in aligning text and melody: " + str(err),
                )
                text_and_mel = None
            context["syllabized_text_with_melody"] = text_and_mel

        context["user_can_proofread_chant"] = (
            self.user_is_editor and self.user_assigned_to_source(self.source)
        )
        # in case the chant has no manuscript_full_text_std_spelling, we check Cantus Index
        # for the expected text for chants with the same Cantus ID, and pass it to the context
        # to suggest it to the user
        cantus_id = chant.cantus_id
        if not cantus_id:
            return context
        if not chant.manuscript_full_text_std_spelling:
            suggested_fulltext = get_suggested_fulltext(chant.cantus_id)
            context["suggested_fulltext"] = suggested_fulltext
        return context

    def get_form_kwargs(self):
        """
        If the request has a data parameter (ie. it is a PUT or POST request),
        we copy the data and add the source id to it.
        """
        kwargs = super().get_form_kwargs()
        if "data" in kwargs:
            kwargs["data"] = kwargs["data"].copy()
            kwargs["data"]["source"] = self.source.id
        return kwargs

    def form_valid(self, form):
        user: User = self.request.user
        chant: Chant = form.instance

        user_can_proofread_chant = self.user_is_editor and self.user_assigned_to_source(
            chant.source
        )

        if not user_can_proofread_chant:
            # Preserve the original values for proofreader-specific fields
            original_chant: Chant = self.get_object()
            chant.chant_range = original_chant.chant_range
            chant.volpiano_proofread = original_chant.volpiano_proofread
            chant.manuscript_full_text_std_proofread = (
                original_chant.manuscript_full_text_std_proofread
            )
            chant.manuscript_full_text_proofread = (
                original_chant.manuscript_full_text_proofread
            )
            chant.other_fields_proofread = original_chant.other_fields_proofread
            proofreaders: list[Optional[User]] = list(original_chant.proofread_by.all())

            # Handle proofreader checkboxes
            if "volpiano" in form.changed_data:
                chant.volpiano_proofread = False
            if "manuscript_full_text_std_spelling" in form.changed_data:
                chant.manuscript_full_text_std_proofread = False
            if "manuscript_full_text" in form.changed_data:
                chant.manuscript_full_text_proofread = False

            # Check if any other fields have changed
            excluded_fields = {
                "volpiano",
                "manuscript_full_text_std_spelling",
                "manuscript_full_text",
            }
            if any(field not in excluded_fields for field in form.changed_data):
                chant.other_fields_proofread = False

        chant.last_updated_by = user
        return_response: HttpResponse = super().form_valid(form)

        # The many-to-many `proofread_by` field is reset when the
        # parent class's `form_valid` method calls `save()` on the model instance.
        if not user_can_proofread_chant:
            chant.proofread_by.set(proofreaders)
        messages.success(self.request, "Chant updated successfully!")
        return return_response

    def form_invalid(self, form):
        """
        If the form is invalid with an error message on the
        manuscript_full_text_std_spelling field ("Field cannot be blank
        on this chant"), we display the edit form with all edited data
        but the original manuscript_full_text_std_spelling field value.
        """
        if form.has_error("manuscript_full_text_std_spelling", "txt-req-prev-existing"):
            data = self.request.POST.copy()
            data["manuscript_full_text_std_spelling"] = form[
                "manuscript_full_text_std_spelling"
            ].initial
            form.data = data
            return super().form_invalid(form)
        return super().form_invalid(form)

    def get_success_url(self) -> str:
        # Take user back to the referring page
        # `ref` url parameter is used to indicate referring page
        next_url = self.request.GET.get("ref")
        # `referrer` is a client-supplied form field, so it can't be trusted as a
        # redirect target unless it points back at this site. This also rejects a
        # missing or empty referrer, which would otherwise redirect to nowhere.
        referrer = self.request.POST.get("referrer")
        referrer_is_safe = url_has_allowed_host_and_scheme(
            referrer,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        )
        if next_url and referrer_is_safe:
            # Return to the edited chant's row so the user keeps their place in
            # the (often very long) chant list rather than landing at the top (#1433).
            return f"{referrer}#chant-{self.object.pk}"
        # ref not found, stay on the same page after save
        return self.request.get_full_path()


class ChantEditSyllabificationView(CustomAccessMixin, UpdateView):  # type: ignore[type-arg]
    template_name = "chant_syllabification_edit.html"
    model = Chant
    context_object_name = "chant"
    form_class = ChantEditSyllabificationForm
    pk_url_kwarg = "chant_id"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flattened_syls_text = ""

    def test_func(self) -> bool:
        chant = self.get_object()
        source = chant.source
        return self.user_assigned_to_source(source)

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
        try:
            syls_text, _ = syllabify_text(
                text=chant.get_best_text_for_syllabizing(),
                clean_text=True,
                text_presyllabified=has_syl_text,
            )
            self.flattened_syls_text = flatten_syllabified_text(syls_text)
        except LatinError as err:
            messages.error(
                self.request,
                "Error in syllabifying text: " + str(err),
            )
            syls_text = None
            self.flattened_syls_text = ""
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
