from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Prefetch, Value
from django.db.models import QuerySet
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import (
    DetailView,
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
)

from main_app.forms import SourceCreateForm, SourceEditForm
from main_app.models import (
    Century,
    Chant,
    Feast,
    Genre,
    Provenance,
    Segment,
    Source,
)
from main_app.permissions import (
    user_can_create_sources,
    user_can_edit_source,
    user_can_view_source,
    user_can_manage_source_editors,
)
from main_app.views.chant import (
    get_feast_selector_options,
    user_can_edit_chants_in_source,
)

CANTUS_SEGMENT_ID = 4063
BOWER_SEGMENT_ID = 4064


class SourceBrowseChantsView(ListView):
    """The view for the `Browse Chants` page.

    Displays a list of Chant objects, accessed with ``chants`` followed by a series of GET params

    ``GET`` parameters:
        ``feast``: Filters by Feast of Chant
        ``search_text``: Filters by text of Chant
        ``genre``: Filters by genre of Chant
        ``folio``: Filters by folio of Chant
    """

    model = Chant
    paginate_by = 100
    context_object_name = "chants"
    template_name = "browse_chants.html"
    pk_url_kwarg = "source_id"

    def get_queryset(self):
        """Gather the chants to be displayed.

        When in the `browse chants` page, there must be a source specified.
        The chants in the specified source are filtered by a set of optional search parameters.

        Returns:
            queryset: The Chant objects to be displayed.
        """
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = get_object_or_404(Source, id=source_id)

        display_unpublished = self.request.user.is_authenticated
        if (source.published is False) and (not display_unpublished):
            raise PermissionDenied()

        # optional search params
        feast_id = self.request.GET.get("feast")
        genre_id = self.request.GET.get("genre")
        folio = self.request.GET.get("folio")
        search_text = self.request.GET.get("search_text")

        # get all chants in the specified source
        chants = source.chant_set.select_related("feast", "office", "genre")
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
        return chants.order_by("folio", "c_sequence")

    def get_context_data(self, **kwargs):
        context: dict = super().get_context_data(**kwargs)
        source_id: int = self.kwargs.get(self.pk_url_kwarg)
        source: Source = get_object_or_404(Source, id=source_id)
        if source.segment_id != CANTUS_SEGMENT_ID:
            # the chant list ("Browse Chants") page should only be visitable
            # for sources in the CANTUS Database segment, as sources in the Bower
            # segment contain no chants
            raise Http404()

        context["source"] = source

    # these are needed in the selectors on the left side of the page
        context["feasts"] = Feast.objects.all().order_by("name")
        context["genres"] = Genre.objects.all().order_by("name")

        display_unpublished: bool = self.request.user.is_authenticated

        # sources in the Bower Segment contain only Sequences and no Chants,
        # so they should not appear among the list of sources
        cantus_segment: QuerySet[Segment] = Segment.objects.get(id=CANTUS_SEGMENT_ID)

        # to be displayed in the "Source" dropdown in the form
        sources: QuerySet[Source] = cantus_segment.source_set.select_related(
            "holding_institution", "segment"
        ).order_by("holding_institution__siglum")
        if not display_unpublished:
            sources = sources.filter(published=True)
        context["sources"] = sources

        user = self.request.user
        context["user_can_edit_chant"] = user_can_edit_chants_in_source(user, source)

        chants_in_source: QuerySet[Chant] = source.chant_set
        if chants_in_source.count() == 0:
            # these are needed in the selectors and hyperlinks on the right side of the page
            # if there's no chant in the source, there should be no options in those selectors
            context["folios"] = None
            context["feasts_with_folios"] = None
            context["previous_folio"] = None
            context["next_folio"] = None
            return context

        # generate options for the folio selector on the right side of the page
        folios: tuple[str] = (
            chants_in_source.values_list("folio", flat=True)
            .distinct()
            .order_by("folio")
        )
        context["folios"] = folios

        if self.request.GET.get("folio"):
            # if browsing chants on a specific folio
            folio: str = self.request.GET.get("folio")
            index: int = list(folios).index(folio)
            # get the previous and next folio, if available
            context["previous_folio"] = folios[index - 1] if index != 0 else None
            context["next_folio"] = (
                folios[index + 1] if index < len(folios) - 1 else None
            )

        # the options for the feast selector on the right, same as the source detail page
        context["feasts_with_folios"] = get_feast_selector_options(source)
        return context


class SourceDetailView(DetailView):
    model = Source
    context_object_name = "source"
    template_name = "source_detail.html"

    def get_queryset(self):
        return self.model.objects.select_related(
            "holding_institution", "segment", "provenance"
        ).all()

    def get_context_data(self, **kwargs):
        source = self.get_object()
        user = self.request.user

        if not user_can_view_source(user, source):
            raise PermissionDenied()

        context = super().get_context_data(**kwargs)

        if source.segment and source.segment_id == BOWER_SEGMENT_ID:
            # if this is a sequence source
            sequences = source.sequence_set.select_related("genre", "office")
            context["sequences"] = sequences.order_by("s_sequence")
            context["folios"] = (
                sequences.values_list("folio", flat=True).distinct().order_by("folio")
            )
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

        context["user_can_edit_chants"] = user_can_edit_chants_in_source(user, source)
        context["user_can_edit_source"] = user_can_edit_source(user, source)
        context["user_can_manage_source_editors"] = user_can_manage_source_editors(user)
        return context


class SourceListView(ListView):
    model = Source
    paginate_by = 100
    context_object_name = "sources"
    template_name = "source_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["provenances"] = (
            Provenance.objects.all().order_by("name").values("id", "name")
        )
        context["centuries"] = (
            Century.objects.all().order_by("name").values("id", "name")
        )
        return context

    def get_queryset(self):
        # use select_related() for foreign keys to reduce DB queries
        queryset = Source.objects.select_related(
            "segment", "provenance", "holding_institution"
        ).order_by("siglum")

        display_unpublished: bool = self.request.user.is_authenticated
        if display_unpublished:
            q_obj_filter = Q()
        else:
            q_obj_filter = Q(published=True)

        if self.request.GET.get("century"):
            century_name = Century.objects.get(id=self.request.GET.get("century")).name
            q_obj_filter &= Q(century__name__icontains=century_name)

        if self.request.GET.get("provenance"):
            provenance_id = int(self.request.GET.get("provenance"))
            q_obj_filter &= Q(provenance__id=provenance_id)
        if self.request.GET.get("segment"):
            segment_id = int(self.request.GET.get("segment"))
            q_obj_filter &= Q(segment__id=segment_id)
        if self.request.GET.get("fullSource") in ["true", "false"]:
            full_source_str = self.request.GET.get("fullSource")
            if full_source_str == "true":
                full_source_q = Q(full_source=True) | Q(full_source=None)
                q_obj_filter &= full_source_q
            else:
                q_obj_filter &= Q(full_source=False)

        if self.request.GET.get("general"):
            # Strip spaces at the beginning and end. Then make list of terms split on spaces
            general_search_terms = self.request.GET.get("general").strip(" ").split(" ")
            # We need a Q Object for each field we're gonna look into
            shelfmark_q = Q()
            siglum_q = Q()
            holding_institution_q = Q()
            holding_institution_city_q = Q()
            description_q = Q()
            # it seems that old cantus don't look into title and provenance for the general search terms
            # cantus.uwaterloo.ca/source/123901 this source cannot be found by searching its provenance 'Kremsmünster' in the general search field
            # provenance_q = Q()
            summary_q = Q()

            # For each term, add it to the Q object of each field with an OR operation.
            # We split the terms so that the words can be separated in the actual
            # field, allowing for a more flexible search, and a field needs
            # to match only one of the terms
            for term in general_search_terms:
                holding_institution_q |= Q(holding_institution__name__icontains=term)
                holding_institution_city_q |= Q(
                    holding_institution__city__icontains=term
                )
                shelfmark_q |= Q(shelfmark__unaccent__icontains=term)
                siglum_q |= Q(holding_institution__siglum__unaccent__icontains=term)
                description_q |= Q(description__unaccent__icontains=term)
                summary_q |= Q(summary__unaccent__icontains=term)
                # provenance_q |= Q(provenance__name__icontains=term)
            # All the Q objects are put together with OR.
            # The end result is that at least one term has to match in at least one
            # field
            # general_search_q = (
            #     title_q | siglum_q | description_q | provenance_q
            # )
            general_search_q = (
                shelfmark_q
                | siglum_q
                | description_q
                | summary_q
                | holding_institution_q
                | holding_institution_city_q
            )
            q_obj_filter &= general_search_q

        # For the indexing notes search we follow the same procedure as above but with
        # different fields
        if self.request.GET.get("indexing"):
            # Make list of terms split on spaces
            indexing_search_terms = self.request.GET.get("indexing").split(" ")
            # We need a Q Object for each field we're gonna look into
            inventoried_by_q = Q()
            full_text_entered_by_q = Q()
            melodies_entered_by_q = Q()
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
                | proofreaders_q
                | other_editors_q
                | indexing_notes_q
            )
            q_obj_filter &= indexing_search_q

        return (
            queryset.filter(q_obj_filter)
            .distinct()
            .prefetch_related(
                Prefetch("century", queryset=Century.objects.all().order_by("id"))
            )
        )


class SourceCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Source
    template_name = "source_create.html"
    form_class = SourceCreateForm

    def test_func(self):
        user = self.request.user
        return user_can_create_sources(user)

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


class SourceDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """The view for deleting a source object

    This view is linked to in the source-edit page.
    """

    model = Source
    template_name = "source_delete.html"

    def test_func(self):
        user = self.request.user
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = get_object_or_404(Source, id=source_id)
        return user_can_edit_source(user, source)

    def get_success_url(self):
        # redirect to homepage
        return "/"


class SourceEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = "source_edit.html"
    model = Source
    form_class = SourceEditForm
    pk_url_kwarg = "source_id"

    def get_context_data(self, **kwargs):
        source = self.get_object()
        context = super().get_context_data(**kwargs)

        if source.segment and source.segment.id == BOWER_SEGMENT_ID:
            # if this is a sequence source
            context["sequences"] = source.sequence_set.order_by("s_sequence")
            context["folios"] = (
                source.sequence_set.values_list("folio", flat=True)
                .distinct()
                .order_by("folio")
            )
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
        return context

    def test_func(self):
        user = self.request.user
        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = get_object_or_404(Source, id=source_id)

        return user_can_edit_source(user, source)

    def form_valid(self, form):
        form.instance.last_updated_by = self.request.user

        # remove this source from the old "current_editors"
        # assign this source to the new "current_editors"

        old_current_editors = list(
            Source.objects.get(id=form.instance.id).current_editors.all()
        )
        new_current_editors = form.cleaned_data["current_editors"]
        source = form.save()

        for old_editor in old_current_editors:
            old_editor.sources_user_can_edit.remove(source)

        for new_editor in new_current_editors:
            new_editor.sources_user_can_edit.add(source)

        return HttpResponseRedirect(self.get_success_url())


class SourceInventoryView(TemplateView):
    template_name = "full_inventory.html"
    pk_url_kwarg = "source_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        source_id = self.kwargs.get(self.pk_url_kwarg)
        source = get_object_or_404(Source, id=source_id)

        display_unpublished = self.request.user.is_authenticated
        if (not display_unpublished) and (source.published == False):
            raise PermissionDenied

        # 4064 is the id for the sequence database
        if source.segment.id == BOWER_SEGMENT_ID:
            queryset = (
                source.sequence_set.annotate(record_type=Value("sequence"))
                .order_by("s_sequence")
                .select_related("genre")
            )
        else:
            queryset = (
                source.chant_set.annotate(record_type=Value("chant"))
                .order_by("folio", "c_sequence")
                .select_related("feast", "office", "genre", "diff_db")
            )

        context["source"] = source
        context["chants"] = queryset

        return context
