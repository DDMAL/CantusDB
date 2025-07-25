import re
from typing import Any, Optional, Union

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.mixins import UserPassesTestMixin
from django.db.models import Q, Prefetch, Value
from django.db.models import QuerySet
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
from main_app.permissions import CustomAccessMixin
from main_app.mixins import JSONResponseMixin

from main_app.views.chant import get_feast_selector_options
from main_app.tasks import save_browse_chants_formset

CANTUS_SEGMENT_ID = 4063
BOWER_SEGMENT_ID = 4064


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

        # to be displayed in the "Source" dropdown in the form
        sources: QuerySet[Source] = (
            cantus_segment.sources.select_related("holding_institution")
            .prefetch_related("segment_m2m")
            .order_by("holding_institution__siglum")
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
            .prefetch_related("segment_m2m", "proofreaders", "inventoried_by")
            .all()
        )

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)

        source = self.object
        if BOWER_SEGMENT_ID in source.segment_m2m.values_list("id", flat=True):
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

        context["user_can_edit_chants"] = self.user_assigned_to_source(source)
        context["user_can_edit_source"] = self.user_assigned_to_source(source) and (
            self.user_is_editor or self.user_created_source(source)
        )
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
        return ["source_lists/source_list.html"]

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
        context["centuries"] = (
            Century.objects.all().order_by("name").values("id", "name")
        )
        context["production_method_choices"] = Source.ProductionMethodChoices.choices
        context["source_completeness_choices"] = (
            Source.SourceCompletenessChoices.choices
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

        if century_id := self.request.GET.get("century"):
            century_name = Century.objects.get(id=century_id).name
            q_obj_filter &= Q(century__name__icontains=century_name)

        if provenance_id := self.request.GET.get("provenance"):
            q_obj_filter &= Q(provenance__id=int(provenance_id))
        if segment_id := self.request.GET.get("segment"):
            q_obj_filter &= Q(segment_m2m__id=int(segment_id))
        if source_completeness := self.request.GET.getlist("sourceCompleteness"):
            q_obj_filter &= Q(source_completeness__in=source_completeness)
        if production_method := self.request.GET.get("prodMethod"):
            q_obj_filter &= Q(production_method=production_method)

        if general_str := self.request.GET.get("general"):
            # Strip spaces at the beginning and end
            general_str = general_str.strip()

            # Use regex to extract quoted and unquoted terms
            quoted_terms = re.findall(
                r'"(.*?)"', general_str
            )  # Extract terms in quotes
            unquoted_terms = re.findall(
                r"\b[\w,-.]+\b", re.sub(r'"(.*?)"', "", general_str)
            )

            # We need a Q Object for each field we're gonna look into
            shelfmark_q = Q()
            siglum_q = Q()
            holding_institution_q = Q()
            holding_institution_city_q = Q()
            description_q = Q()
            name_q = Q()
            # it seems that old cantus don't look into title and provenance
            # for the general search terms
            # cantus.uwaterloo.ca/source/123901 this source cannot be found by searching
            # its provenance 'Kremsmünster' in the general search field
            # provenance_q = Q()
            summary_q = Q()

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

            # Combine all Q objects with OR
            general_search_q = (
                shelfmark_q
                | siglum_q
                | description_q
                | summary_q
                | holding_institution_q
                | holding_institution_city_q
                | name_q
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
                | indexing_notes_q
            )
            q_obj_filter &= indexing_search_q

        order_param = self.request.GET.get("order")
        order_fields = ["holding_institution__siglum", "shelfmark"]
        if order_param == "country":
            order_fields.insert(0, "holding_institution__country")
        elif order_param == "city_institution":
            order_fields.insert(0, "holding_institution__city")
            order_fields.insert(1, "holding_institution__name")
        if self.request.GET.get("sort") == "desc":
            sort_prefix = "-"
        else:
            sort_prefix = ""

        order_by_args = [f"{sort_prefix}{field}" for field in order_fields]

        return (
            queryset.filter(q_obj_filter)
            .order_by(*order_by_args)
            .distinct()
            .prefetch_related(
                Prefetch("century", queryset=Century.objects.all().order_by("id"))
            )
        )


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


class SourceEditView(CustomAccessMixin, UpdateView):  # type: ignore[type-arg]
    template_name = "source_edit.html"
    model = Source
    form_class = SourceEditForm
    pk_url_kwarg = "source_id"

    def test_func(self) -> bool:
        source = self.get_object()
        if self.user_assigned_to_source(source) and (
            self.user_is_editor or source.created_by == self.user
        ):
            return True
        return False

    def get_context_data(self, **kwargs):
        source = self.object
        context = super().get_context_data(**kwargs)

        if settings.BOWER_SEGMENT_ID in source.segment_m2m.values_list("id", flat=True):
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
        return HttpResponseRedirect(self.get_success_url())


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
        if BOWER_SEGMENT_ID in self.source.segment_m2m.values_list("id", flat=True):
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

    def form_valid(self, form: ImageLinkForm) -> HttpResponseRedirect:
        """
        Save the image links to the database.
        """
        form.save(self.object)
        return HttpResponseRedirect(self.get_success_url())
