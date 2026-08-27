import logging
import re
from datetime import date
from functools import cached_property
from typing import Any, Optional, Union

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q, Prefetch, QuerySet, Value, Min, Max
from django.http import (
    HttpResponseRedirect,
    Http404,
    HttpResponse,
    HttpRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import (
    DetailView,
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    FormView,
    View,
)
from django.views.generic.detail import SingleObjectMixin

from main_app.forms import (
    SourceCreateForm,
    SourceEditForm,
    SourceBrowseChantsProofreadForm,
    ImageLinkForm,
    BrowseChantsBulkEditFormset,
)
from main_app.models import (
    Century,
    Chant,
    Feast,
    Genre,
    Provenance,
    Segment,
    Source,
    Institution,
    Sequence,
)
from main_app.models.source_url import SourceURL
from main_app.permissions import CustomAccessMixin
from main_app.mixins import JSONResponseMixin
from main_app.iiif_utils import (
    ManifestTooLargeError,
    fetch_manifest,
    extract_canvases,
    generate_folio_image_mapping,
    mapping_to_csv,
)
from main_app.views.chant import get_feast_selector_options
from main_app.tasks import save_browse_chants_formset

logger = logging.getLogger(__name__)

SOURCE_ADVANCED_SEARCH_FIELDS: tuple[str, ...] = (
    # GET params belonging to the collapsible "Advanced search" section of
    # source_list.html / canadian_chant_db.html / cantorales.html / ccdb_browse.html;
    # used to auto-expand it when any of them are set. These are all "plain" fields
    # with no value unless the user actually filled them in.
    #
    # "segment", "dateStart"/"dateEnd", and "sourceCompleteness" are handled
    # separately in get_context_data: their widgets always submit a value on
    # Apply (the full slider range, all checkboxes checked, or a segment
    # already scoped via the URL on CCDB/Cantorales) even when the user
    # hasn't changed anything from the default, so a naive presence check
    # would keep the section expanded after every single search.
    "country",
    "provenance",
    "prodMethod",
    "indexing",
)


class SourceBrowseChantsView(CustomAccessMixin, ListView):  # type: ignore[type-arg]
    """The view for the `Browse Chants` page.

    Displays a list of Chant objects, accessed with ``chants`` followed by a series of GET params

    ``GET`` parameters:
        ``feast``: Filters by Feast of Chant
        ``search_text``: Filters by text of Chant
        ``genre``: Filters by genre of Chant
        ``folio``: Filters by folio of Chant
        ``manuscript_full_text_proofread``: Filters by chants that have their full text proofread
        ``manuscript_full_text_std_proofread``: Filters by chants that have their standardized
        spelling full text proofread
        ``volpiano_proofread``: Filters by chants that have their volpiano proofread
    """

    model = Chant
    paginate_by = 100
    context_object_name = "chants"
    template_name = "browse_chants.html"
    pk_url_kwarg = "source_id"
    source: Source
    extra_context = {
        "bulk_edit_formset": None,
    }

    def test_func(self) -> bool:
        """
        `GET` requests allowed for published sources or sources the user can edit.
        `POST` requests allowed only for sources the user can edit.
        """
        source_id = self.kwargs.get(self.pk_url_kwarg)
        self.source = get_object_or_404(Source, id=source_id)
        if self.request.method == "POST":
            return self.user_assigned_to_source(self.source)
        return (
            self.source.published
            or self.user_is_global_viewer
            or self.user_assigned_to_source(self.source)
        )

    def get_queryset(self) -> QuerySet[Chant]:
        """
        Gather the chants to be displayed.

        The chants in the specified source are filtered by a set of optional search parameters.

        Returns:
            queryset: The Chant objects to be displayed.
        """
        # optional search params
        feast_id = self.request.GET.get("feast")
        genre_id = self.request.GET.get("genre")
        folio = self.request.GET.get("folio")
        search_text = self.request.GET.get("search_text")

        # proofread fields filter
        manuscript_full_text_proofread = self.request.GET.get(
            "manuscript_full_text_proofread"
        )
        manuscript_full_text_std_proofread = self.request.GET.get(
            "manuscript_full_text_std_proofread"
        )
        volpiano_proofread = self.request.GET.get("volpiano_proofread")

        other_fields_proofread = self.request.GET.get("other_fields_proofread")

        # get all chants in the specified source
        chants: QuerySet[Chant] = self.source.chant_set.select_related(
            "feast", "service", "genre"
        )
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
        # Apply proofreading filters if they are set
        if manuscript_full_text_std_proofread:
            q_obj = Q(manuscript_full_text_std_spelling__isnull=False) & ~Q(
                manuscript_full_text_std_spelling=""
            )
            if manuscript_full_text_std_proofread == "True":
                q_obj &= Q(manuscript_full_text_std_proofread="True")
            else:  # manuscript_full_text_std_proofread == "False"
                q_obj &= ~Q(manuscript_full_text_std_proofread="True")
            chants = chants.filter(q_obj)

        if manuscript_full_text_proofread:
            q_obj = Q(manuscript_full_text__isnull=False) & ~Q(manuscript_full_text="")
            if manuscript_full_text_proofread == "True":
                q_obj &= Q(manuscript_full_text_proofread="True")
            else:  # manuscript_full_text_proofread == "False"
                q_obj &= ~Q(manuscript_full_text_proofread="True")
            chants = chants.filter(q_obj)

        if volpiano_proofread:
            q_obj = Q(volpiano__isnull=False) & ~Q(volpiano="")
            if volpiano_proofread == "True":
                q_obj &= Q(volpiano_proofread="True")
            else:  # volpiano_proofread == "False"
                q_obj &= ~Q(volpiano_proofread="True")
            chants = chants.filter(q_obj)

        if other_fields_proofread:
            if other_fields_proofread == "True":
                q_obj = Q(other_fields_proofread=True)
            else:  # other_fields_proofread == "False"
                q_obj = Q(other_fields_proofread=False)
            chants = chants.filter(q_obj)

        return chants.order_by("folio", "c_sequence")

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context: dict[str, Any] = super().get_context_data(**kwargs)
        source: Source = self.source

        # Check if source has any chants - if not, return 404
        if not source.chant_set.exists():
            raise Http404()

        context["source"] = source

        # these are needed in the selectors on the left side of the page
        context["feasts"] = Feast.objects.all().order_by("name")
        context["genres"] = Genre.objects.all().order_by("name")

        display_unpublished: bool = self.request.user.is_authenticated

        # sources in the Bower Segment contain only Sequences and no Chants,
        # so they should not appear among the list of sources
        cantus_segment: Segment = Segment.objects.get(id=settings.CANTUS_SEGMENT_ID)

        # to be displayed in the "Source" dropdown in the form.
        # Always include the current source so it can be marked as selected,
        # even if it doesn't belong to the CantusDatabase segment.
        sources: QuerySet[Source] = (
            Source.objects.filter(Q(segment_m2m=cantus_segment) | Q(id=source.id))
            .select_related("holding_institution")
            .prefetch_related("segment_m2m")
            .order_by("holding_institution__siglum", "shelfmark", "id")
            .distinct()
        )
        if not display_unpublished:
            sources = sources.filter(published=True)
        context["sources"] = sources

        context["user_can_edit_chant"] = self.user_assigned_to_source(source)
        context["user_can_proofread_source"] = (
            self.user_assigned_to_source(source) and self.user_is_editor
        )

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

        if folio := self.request.GET.get("folio"):
            # if browsing chants on a specific folio
            index: int = list(folios).index(folio)
            # get the previous and next folio, if available
            context["previous_folio"] = folios[index - 1] if index != 0 else None
            context["next_folio"] = (
                folios[index + 1] if index < len(folios) - 1 else None
            )

        # the options for the feast selector on the right, same as the source detail page
        context["feasts_with_folios"] = get_feast_selector_options(source)
        context["proofread_filter_form"] = SourceBrowseChantsProofreadForm(
            self.request.GET or None
        )
        if not self.extra_context.get("bulk_edit_formset"):
            context["bulk_edit_formset"] = BrowseChantsBulkEditFormset(
                queryset=context["object_list"]
            )
        return context

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        chant_ids = list(self.get_queryset().values_list("id", flat=True))
        task = save_browse_chants_formset.delay(
            data=request.POST,
            chant_ids=chant_ids,
        )
        return JsonResponse({"taskID": task.id})


class SourceDetailView(CustomAccessMixin, JSONResponseMixin, DetailView):  # type: ignore[type-arg]
    model = Source
    context_object_name = "source"
    template_name = "source_detail.html"
    json_fields = [
        "id",
        "description",
        "provenance__name",
        "date",
        "heading",
        "short_heading",
    ]

    def test_func(self) -> bool:
        source = self.get_object()
        if self.user_is_global_viewer:
            return True
        return self.published_and_assigned_sources.contains(source)

    def get_queryset(self) -> QuerySet[Source]:
        return (
            self.model.objects.select_related(
                "holding_institution", "provenance", "created_by"
            )
            .prefetch_related(
                "segment_m2m",
                "proofreaders",
                "inventoried_by",
                "source_data_contributed_by",
                "full_text_entered_by",
                "melodies_entered_by",
                "other_editors",
                "description_entered_by",
                "source_links",
            )
            .all()
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        source = self.object
        if source.segment_m2m.filter(id=settings.BOWER_SEGMENT_ID).exists():
            # if this is a sequence source
            sequences = source.sequence_set.select_related("genre", "service")
            context["sequences"] = sequences.order_by("s_sequence")
            context["folios"] = (
                sequences.values_list("folio", flat=True).distinct().order_by("folio")
            )
            context["bower_segment"] = True
            context["has_chants"] = sequences.exists()
        else:
            # if this is a chant source
            chants = source.chant_set
            folios = chants.values_list("folio", flat=True).distinct().order_by("folio")
            context["folios"] = folios
            # the options for the feast selector on the right, only chant sources have this
            context["feasts_with_folios"] = get_feast_selector_options(source)
            context["bower_segment"] = False
            context["has_chants"] = chants.exists()

        context["source_notation"] = source.notation.first()
        context["user_can_edit_chants"] = self.user_assigned_to_source(source)
        context["user_can_edit_source"] = self.user_can_edit_source(source)
        return context


class SourceListView(CustomAccessMixin, ListView):  # type: ignore[type-arg]
    model = Source
    paginate_by = 100
    context_object_name = "sources"
    segment: Optional[Segment] = None
    test_req = False

    def get_template_names(self) -> list[str]:
        if self.segment and self.segment.id == 4066:
            return ["source_lists/canadian_chant_db.html"]
        elif self.segment and self.segment.id == 4067:
            return ["source_lists/cantorales.html"]
        return ["source_lists/source_list.html"]

    @cached_property
    def date_range_bounds(self) -> tuple[Optional[int], Optional[int]]:
        """
        Year-range slider bounds. Endpoints are rounded out to the nearest
        multiple of 5 so the slider's step="5" reaches both. The upper bound
        is clipped to the current multiple of 5 so future-dated centuries
        (e.g. a "21st century" stub ending in 2099) do not stretch the
        slider past today.
        """
        current_year_rounded = (date.today().year // 5) * 5
        century_dates = Century.objects.filter(
            min_date__isnull=False, max_date__isnull=False
        ).aggregate(
            min_year=Min("min_date"),
            max_year=Max("max_date"),
        )
        min_year = century_dates["min_year"]
        max_year = century_dates["max_year"]
        date_range_min = (min_year // 5) * 5 if min_year is not None else None
        date_range_max = (
            min(-(-max_year // 5) * 5, current_year_rounded)
            if max_year is not None
            else None
        )
        return date_range_min, date_range_max

    @cached_property
    def requested_date_range(self) -> tuple[Optional[int], Optional[int]]:
        """
        The dateStart/dateEnd query parameters parsed to ints. A missing or
        non-numeric value becomes None rather than raising, so a mangled
        querystring can't break the source list.
        """

        def parse(param: str) -> Optional[int]:
            raw = self.request.GET.get(param)
            if not raw:
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        return parse("dateStart"), parse("dateEnd")

    @cached_property
    def date_range_active(self) -> bool:
        """
        True only when the requested range actually narrows the full range of
        dated sources (a bound sits strictly inside the outer bounds). When
        the slider is untouched the form still submits the outer bounds, so
        comparing against them keeps us from applying a century filter the
        user never asked for -- which would silently drop every source that
        has no century assigned. The numeric comparison also shrugs off
        differently-formatted or hand-edited querystrings.
        """
        date_range_min, date_range_max = self.date_range_bounds
        requested_start, requested_end = self.requested_date_range
        narrows_start = (
            requested_start is not None
            and date_range_min is not None
            and requested_start > date_range_min
        )
        narrows_end = (
            requested_end is not None
            and date_range_max is not None
            and requested_end < date_range_max
        )
        return narrows_start or narrows_end

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["countries"] = (
            Institution.objects.values_list("country", flat=True)
            .distinct()
            .order_by("country")
        )
        context["provenances"] = (
            Provenance.objects.all().order_by("name").values("id", "name")
        )
        context["date_range_min"], context["date_range_max"] = self.date_range_bounds

        context["production_method_choices"] = Source.ProductionMethodChoices.choices
        context["source_completeness_choices"] = (
            Source.SourceCompletenessChoices.choices
        )

        selected_completeness = set(self.request.GET.getlist("sourceCompleteness"))
        all_completeness_values = {
            str(value) for value, _ in Source.SourceCompletenessChoices.choices
        }
        source_completeness_active = bool(selected_completeness) and (
            selected_completeness != all_completeness_values
        )

        # "segment" only counts as an active advanced filter on the
        # unscoped source list; on CCDB/Cantorales it's already fixed by
        # the URL and the field doesn't even appear in those templates.
        segment_active = not self.segment and bool(self.request.GET.get("segment"))

        # The radio group always submits a value once touched; "all" is its
        # default, so only a non-default value counts as active.
        inventoried_active = self.request.GET.get("inventoried") in (
            "inventoried",
            "nonInventoried",
        )

        context["advanced_search_active"] = (
            any(self.request.GET.get(field) for field in SOURCE_ADVANCED_SEARCH_FIELDS)
            or self.date_range_active
            or source_completeness_active
            or segment_active
            or inventoried_active
        )
        return context

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        segment_id = self.kwargs.get("segment_id")
        if segment_id:
            self.segment = get_object_or_404(Segment, id=segment_id)
        return super().get(request, *args, **kwargs)

    def get_queryset(self) -> QuerySet[Source]:
        if self.user.is_superuser or self.user_is_global_viewer:
            queryset = Source.objects.select_related(
                "provenance", "holding_institution"
            ).prefetch_related("segment_m2m")
        else:
            queryset = self.published_and_assigned_sources.select_related(
                "provenance", "holding_institution"
            ).prefetch_related("segment_m2m")

        q_obj_filter = Q()

        if self.segment:
            q_obj_filter &= Q(segment_m2m=self.segment)

        if country_name := self.request.GET.get("country"):
            q_obj_filter &= Q(holding_institution__country__icontains=country_name)

        # Handle direct date range filtering (e.g., 1400-1500) by keeping only
        # sources with a century that overlaps the range. This is skipped when
        # the range still spans the full extent of dated sources -- see
        # date_range_active -- so leaving the slider untouched does not drop
        # sources that simply have no century assigned.
        if self.date_range_active:
            date_start_int, date_end_int = self.requested_date_range
            if date_start_int is not None and date_end_int is not None:
                # Both dates specified: find centuries that overlap the range
                q_obj_filter &= Q(
                    century__min_date__lte=date_end_int,
                    century__max_date__gte=date_start_int,
                )
            elif date_start_int is not None:
                # Only start date: find centuries that haven't ended
                q_obj_filter &= Q(century__max_date__gte=date_start_int)
            elif date_end_int is not None:
                # Only end date: find centuries that have started
                q_obj_filter &= Q(century__min_date__lte=date_end_int)

        if provenance_id := self.request.GET.get("provenance"):
            q_obj_filter &= Q(provenance__id=int(provenance_id))
        if segment_id := self.request.GET.get("segment"):
            q_obj_filter &= Q(segment_m2m__id=int(segment_id))
        if source_completeness := self.request.GET.getlist("sourceCompleteness"):
            q_obj_filter &= Q(source_completeness__in=source_completeness)
        if production_method := self.request.GET.get("prodMethod"):
            q_obj_filter &= Q(production_method=production_method)
        inventoried_filter = self.request.GET.get("inventoried")
        if inventoried_filter == "nonInventoried":
            q_obj_filter &= Q(number_of_chants__isnull=True) | Q(number_of_chants=0)
        elif inventoried_filter == "inventoried":
            q_obj_filter &= Q(number_of_chants__gt=0)

        if general_str := self.request.GET.get("general"):
            # Strip leading/trailing spaces and collapse internal whitespace
            general_str = " ".join(general_str.split())

            # Use regex to extract quoted and unquoted terms
            quoted_terms = re.findall(
                r'"(.*?)"', general_str
            )  # Extract terms in quotes
            unquoted_terms = re.findall(
                r"\b[\w,-.:]+\b", re.sub(r'"(.*?)"', "", general_str)
            )

            # We need a Q Object for each field we're gonna look into
            shelfmark_q = Q()
            siglum_q = Q()
            holding_institution_q = Q()
            holding_institution_city_q = Q()
            description_q = Q()
            name_q = Q()
            summary_q = Q()
            provenance_q = Q()
            fragmentarium_id_q = Q()
            dact_id_q = Q()
            identifiers_q = Q()

            # Add unquoted terms to the Q object with partial matching (icontains)
            for term in unquoted_terms:
                holding_institution_q |= Q(
                    holding_institution__name__unaccent__icontains=term
                )
                holding_institution_city_q |= Q(
                    holding_institution__city__unaccent__icontains=term
                )
                shelfmark_q |= Q(shelfmark__unaccent__icontains=term)
                siglum_q |= Q(holding_institution__siglum__unaccent__icontains=term)
                description_q |= Q(description__unaccent__icontains=term)
                summary_q |= Q(summary__unaccent__icontains=term)
                name_q |= Q(name__unaccent__icontains=term)
                provenance_q |= Q(provenance__name__unaccent__icontains=term)
                fragmentarium_id_q |= Q(fragmentarium_id__icontains=term)
                dact_id_q |= Q(dact_id__icontains=term)
                identifiers_q |= Q(identifiers__identifier__unaccent__icontains=term)

            # Add quoted terms to the Q object with exact matching (iexact)
            for term in quoted_terms:
                holding_institution_q |= Q(
                    holding_institution__name__unaccent__icontains=term
                )
                holding_institution_city_q |= Q(
                    holding_institution__city__unaccent__icontains=term
                )
                shelfmark_q |= Q(shelfmark__unaccent__icontains=term)
                siglum_q |= Q(holding_institution__siglum__unaccent__icontains=term)
                description_q |= Q(description__unaccent__icontains=term)
                summary_q |= Q(summary__unaccent__icontains=term)
                name_q |= Q(name__unaccent__icontains=term)
                provenance_q |= Q(provenance__name__unaccent__icontains=term)
                fragmentarium_id_q |= Q(fragmentarium_id__icontains=term)
                dact_id_q |= Q(dact_id__icontains=term)
                identifiers_q |= Q(identifiers__identifier__unaccent__icontains=term)

            # Combine all Q objects with OR
            general_search_q = (
                shelfmark_q
                | siglum_q
                | description_q
                | summary_q
                | holding_institution_q
                | holding_institution_city_q
                | name_q
                | provenance_q
                | fragmentarium_id_q
                | dact_id_q
                | identifiers_q
            )

            # Apply the general search Q object to the filter
            q_obj_filter &= general_search_q

        # For the indexing notes search we follow the same procedure as above but with
        # different fields
        if indexing_str := self.request.GET.get("indexing"):
            # Make list of terms split on spaces
            indexing_search_terms = indexing_str.strip(" ").split(" ")
            # We need a Q Object for each field we're gonna look into
            inventoried_by_q = Q()
            full_text_entered_by_q = Q()
            melodies_entered_by_q = Q()
            description_entered_by_q = Q()
            proofreaders_q = Q()
            other_editors_q = Q()
            source_data_contributed_by_q = Q()
            indexing_notes_q = Q()
            # For each term, add it to the Q object of each field with an OR operation.
            # We split the terms so that the words can be separated in the actual
            # field, allowing for a more flexible search, and a field needs
            # to match only one of the terms
            for term in indexing_search_terms:
                inventoried_by_q |= Q(inventoried_by__full_name__icontains=term)
                full_text_entered_by_q |= Q(
                    full_text_entered_by__full_name__icontains=term
                )
                melodies_entered_by_q |= Q(
                    melodies_entered_by__full_name__icontains=term
                )
                description_entered_by_q |= Q(
                    description_entered_by__full_name__icontains=term
                )
                proofreaders_q |= Q(proofreaders__full_name__icontains=term)
                other_editors_q |= Q(other_editors__full_name__icontains=term)
                source_data_contributed_by_q |= Q(
                    source_data_contributed_by__full_name__icontains=term
                )
                indexing_notes_q |= Q(indexing_notes__icontains=term)
            # All the Q objects are put together with OR.
            # The end result is that at least one term has to match in at least one
            # field
            indexing_search_q = (
                inventoried_by_q
                | full_text_entered_by_q
                | melodies_entered_by_q
                | description_entered_by_q
                | proofreaders_q
                | other_editors_q
                | source_data_contributed_by_q
                | indexing_notes_q
            )
            q_obj_filter &= indexing_search_q

        order_param = self.request.GET.get("order")
        sort_desc = self.request.GET.get("sort") == "desc"
        sort_prefix = "-" if sort_desc else ""

        if order_param == "country":
            # Order private collectors (whose siglum is NULL) after institutions
            # with sigla within the same country group. PostgreSQL's native default
            # already does this: NULLS LAST for ascending order, NULLS FIRST for
            # descending order, which matches the Python sort used in tests
            # (`(siglum is None, siglum or "")`) once the whole list is reversed
            # for a descending sort. A final `id` tiebreaker keeps ordering
            # deterministic when country/siglum/shelfmark are all equal.
            order_by_args = [
                f"{sort_prefix}holding_institution__country",
                f"{sort_prefix}holding_institution__siglum",
                f"{sort_prefix}shelfmark",
                f"{sort_prefix}id",
            ]
        elif order_param == "city_institution":
            order_by_args = [
                f"{sort_prefix}holding_institution__city",
                f"{sort_prefix}holding_institution__name",
                f"{sort_prefix}holding_institution__siglum",
                f"{sort_prefix}shelfmark",
                f"{sort_prefix}id",
            ]
        else:
            order_by_args = [
                f"{sort_prefix}holding_institution__siglum",
                f"{sort_prefix}shelfmark",
                f"{sort_prefix}id",
            ]

        return (
            queryset.filter(q_obj_filter)
            .order_by(*order_by_args)
            .distinct()
            .prefetch_related(
                Prefetch("century", queryset=Century.objects.all().order_by("id")),
                # Read by Source.external_images_url for the sidebar/table image
                # link; without it each source on the page costs a query.
                "source_links",
            )
        )


class CcdbBrowseView(SourceListView):
    """Browse/search view for the Canadian Chant Database sources page."""

    def get_template_names(self) -> list[str]:
        return ["source_lists/ccdb_browse.html"]


class SourceCreateView(UserPassesTestMixin, CreateView):  # type: ignore[type-arg]
    model = Source
    template_name = "source_create.html"
    form_class = SourceCreateForm

    def test_func(self) -> bool:
        user = self.request.user
        return user.is_authenticated

    def get_success_url(self):
        return reverse("source-detail", args=[self.object.id])

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        form.instance.last_updated_by = self.request.user
        self.object = form.save()

        # assign this source to the "current_editors"
        current_editors = self.object.current_editors.all()
        self.request.user.sources_user_can_edit.add(self.object)

        for editor in current_editors:
            editor.sources_user_can_edit.add(self.object)

        messages.success(
            self.request,
            "Source created successfully!",
        )
        return HttpResponseRedirect(self.get_success_url())


class SourceDeleteView(CustomAccessMixin, DeleteView):  # type: ignore[type-arg]
    """
    The view for deleting a source object

    This view is linked to in the source-edit page.
    """

    object: Source  # type hint to avoid typing error
    model = Source
    template_name = "source_delete.html"
    success_url = "/"

    def test_func(self) -> bool:
        return self.user_is_editor and self.user_assigned_to_source(self.get_object())


PROOFREADING_SUBMITTED_MESSAGE = (
    "Source submitted for proofreading. You can still view it, but "
    "editing is now locked until an editor picks it up."
)


class SourceEditView(CustomAccessMixin, UpdateView):  # type: ignore[type-arg]
    template_name = "source_edit.html"
    model = Source
    form_class = SourceEditForm
    pk_url_kwarg = "source_id"

    def test_func(self) -> bool:
        return self.user_can_edit_source(self.get_object())

    def get_context_data(self, **kwargs):
        source = self.object
        context = super().get_context_data(**kwargs)

        if source.segment_m2m.filter(id=settings.BOWER_SEGMENT_ID).exists():
            # if this is a sequence source
            context["sequences"] = source.sequence_set.order_by("s_sequence")
            context["folios"] = (
                source.sequence_set.values_list("folio", flat=True)
                .distinct()
                .order_by("folio")
            )
            context["bower_segment"] = True
        else:
            # if this is a chant source
            folios = (
                source.chant_set.values_list("folio", flat=True)
                .distinct()
                .order_by("folio")
            )
            context["folios"] = folios
            # the options for the feast selector on the right, only chant sources have this
            context["feasts_with_folios"] = get_feast_selector_options(source)
            context["bower_segment"] = False
        return context

    def form_valid(self, form):
        form.instance.last_updated_by = self.request.user
        form.save()
        if "submit_for_proofreading" in self.request.POST:
            # The button lives inside this form, so save the indexer's
            # pending corrections before locking the source (issue #1962).
            source = form.instance
            source.submit_for_proofreading(self.request.user)
            messages.success(self.request, PROOFREADING_SUBMITTED_MESSAGE)
            return HttpResponseRedirect(reverse("source-detail", args=[source.id]))
        return HttpResponseRedirect(self.get_success_url())


class SourceSubmitForProofreadingView(CustomAccessMixin, SingleObjectMixin, View):  # type: ignore[type-arg]
    """
    Lets anyone working on a source mark it as ready for proofreading.
    Sets the source's status accordingly, which locks it from further
    edits by the assigned indexer/creator (though they can still view it)
    until an editor picks it up for proofreading. See issue #1962.

    Anyone assigned to the source may submit it, not only its creator:
    #1962 asks for a way for whoever is working on a source to hand it
    over, and an indexer is routinely assigned to a source someone else
    created.
    """

    model = Source
    pk_url_kwarg = "source_id"

    def test_func(self) -> bool:
        source = self.get_object()
        if not self.user_assigned_to_source(source):
            return False
        if source.source_status == Source.PROOFREAD_PENDING_STATUS:
            # Already submitted, and the submitter has lost edit access. Only
            # editors may resubmit; otherwise a locked-out user could keep
            # rewriting `last_updated_by`/`date_updated` and re-floating the
            # source in the proofreading queue.
            return self.user_is_editor
        return True

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        source = self.get_object()
        source.submit_for_proofreading(request.user)
        messages.success(request, PROOFREADING_SUBMITTED_MESSAGE)
        return HttpResponseRedirect(reverse("source-detail", args=[source.id]))


class SourceInventoryView(CustomAccessMixin, ListView):  # type: ignore[type-arg]
    template_name = "full_inventory.html"
    pk_url_kwarg = "source_id"
    context_object_name = "chants"
    source: Source

    def test_func(self) -> bool:
        source_id = self.kwargs.get(self.pk_url_kwarg)
        self.source = get_object_or_404(Source, id=source_id)
        return (
            self.user_is_global_viewer
            or self.source.published
            or self.user_assigned_to_source(self.source)
        )

    def get_queryset(self) -> Union[QuerySet[Chant], QuerySet[Sequence]]:
        if self.source.segment_m2m.filter(id=settings.BOWER_SEGMENT_ID).exists():
            queryset = (
                self.source.sequence_set.annotate(record_type=Value("sequence"))
                .order_by("s_sequence")
                .select_related("genre")
            )
        else:
            queryset = (
                self.source.chant_set.annotate(record_type=Value("chant"))
                .order_by("folio", "c_sequence")
                .select_related("feast", "service", "genre", "diff_db")
            )

        # Return 404 if no chants/sequences exist
        if not queryset.exists():
            raise Http404()

        return queryset

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context["source"] = self.source
        return context


class SourceAddImageLinksView(CustomAccessMixin, SingleObjectMixin, FormView):  # type: ignore
    template_name = "source_add_image_links.html"
    pk_url_kwarg = "source_id"
    queryset = Source.objects.select_related("holding_institution")
    context_object_name = "source"
    form_class = ImageLinkForm
    object: Source
    http_method_names = ["get", "post"]

    def test_func(self) -> bool:
        return self.user.is_superuser

    def get_success_url(self) -> str:
        return reverse("source-detail", args=[self.object.id])

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        return super().get(request, *args, **kwargs)

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_initial(self) -> dict[str, Any]:
        """
        Set the initial data required by the ImageLinkForm
        on GET requests.
        """
        folios: QuerySet[Chant, Optional[str]] = (
            self.object.chant_set.values_list("folio", flat=True)
            .distinct()
            .order_by("folio")
        )
        return {folio: "" for folio in folios if folio}

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        # Check if this source has a IIIF manifest
        has_iiif = self.object.source_links.filter(
            url_type=SourceURL.URLTypes.IIIF_MANIFEST
        ).exists()
        context["has_iiif_manifest"] = has_iiif
        return context

    def form_valid(self, form: ImageLinkForm) -> HttpResponseRedirect:
        """
        Save the image links to the database.
        """
        form.save(self.object)
        messages.success(self.request, "Image links saved successfully!")
        return HttpResponseRedirect(self.get_success_url())


class SourceIIIFMappingView(CustomAccessMixin, SingleObjectMixin, View):  # type: ignore
    """
    View to generate a folio-to-image CSV mapping from a source's IIIF manifest.

    Fetches the IIIF manifest, parses canvases, matches them to folios
    in the source, and returns a downloadable CSV file.
    """

    pk_url_kwarg = "source_id"
    queryset = Source.objects.select_related("holding_institution")
    object: Source
    http_method_names = ["get"]

    def test_func(self) -> bool:
        return self.user.is_superuser

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.object = self.get_object()
        redirect_url = reverse("source-add-image-links", args=[self.object.id])

        # Get the IIIF manifest URL for this source
        manifest_link = self.object.source_links.filter(
            url_type=SourceURL.URLTypes.IIIF_MANIFEST
        ).first()

        if not manifest_link:
            messages.error(request, "No IIIF manifest found for this source.")
            return HttpResponseRedirect(redirect_url)

        # Fetch and parse the manifest
        try:
            manifest = fetch_manifest(manifest_link.url)
        except requests.RequestException:
            logger.exception("Failed to fetch IIIF manifest: %s", manifest_link.url)
            messages.error(request, "Failed to fetch IIIF manifest.")
            return HttpResponseRedirect(redirect_url)
        except ManifestTooLargeError:
            logger.exception("IIIF manifest too large: %s", manifest_link.url)
            messages.error(request, "IIIF manifest is too large to process.")
            return HttpResponseRedirect(redirect_url)
        except ValueError:
            logger.exception("Invalid JSON in IIIF manifest: %s", manifest_link.url)
            messages.error(request, "IIIF manifest is not valid JSON.")
            return HttpResponseRedirect(redirect_url)

        # Extract canvases from the manifest
        canvases = extract_canvases(manifest)
        if not canvases:
            messages.error(request, "No canvases found in the IIIF manifest.")
            return HttpResponseRedirect(redirect_url)

        # Get source folios
        source_folios = list(
            self.object.chant_set.values_list("folio", flat=True)
            .distinct()
            .order_by("folio")
        )
        source_folios = [f for f in source_folios if f]

        # Generate the mapping and CSV
        mapping = generate_folio_image_mapping(canvases, source_folios)
        csv_content = mapping_to_csv(mapping)

        # Return as a downloadable CSV
        response = HttpResponse(csv_content, content_type="text/csv")
        source_id = self.object.id
        response["Content-Disposition"] = (
            f'attachment; filename="source_{source_id}_iiif_mapping.csv"'
        )
        return response
