from django.views.generic import DetailView, ListView
from django.db.models import Q
from main_app.models import Source, Provenance, Century
from extra_views import SearchableListMixin


class SourceDetailView(DetailView):
    model = Source
    context_object_name = "source"
    template_name = "source_detail.html"


class SourceListView(ListView):
    model = Source
    queryset = Source.objects.all().order_by("siglum")
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
        queryset = super().get_queryset()
        q_obj_filter = Q()
        if self.request.GET.get("century"):
            century_id = int(self.request.GET.get("century"))
            q_obj_filter &= Q(century__id=century_id)
        if self.request.GET.get("provenance"):
            provenance_id = int(self.request.GET.get("provenance"))
            q_obj_filter &= Q(provenance__id=provenance_id)
        if self.request.GET.get("segment"):
            segment_id = int(self.request.GET.get("segment"))
            q_obj_filter &= Q(segment__id=segment_id)
        if self.request.GET.get("fullsource") in ["true", "false"]:
            full_source_str = self.request.GET.get("fullsource")
            if full_source_str == "true":
                full_source = True
            elif full_source == "false":
                full_source = False
            q_obj_filter &= Q(full_source=full_source)
        # Maybe change this to lookup in a search vector with the vector Postgres field?
        # I would have to add a signal to update the vector with changes like I did
        # with SIMSSADB
        # For the indexing notes search we follow the same procedure as above but with
        # different fields
        if self.request.GET.get("general"):
            # Make list of terms split on spaces
            general_search_terms = self.request.GET.get("general").split(" ")
            # We need a Q Object for each field we're gonna look into
            title_q = Q()
            siglum_q = Q()
            rism_siglum_q = Q()
            description_q = Q()
            provenance_q = Q()
            # For each term, add it to the Q object of each field with an OR operation.
            # We split the terms so that the words can be separated in the actual
            # field, allowing for a more flexible search, and a field needs
            # to match only one of the terms
            for term in general_search_terms:
                title_q |= Q(title__icontains=term)
                siglum_q |= Q(siglum__icontains=term)
                rism_siglum_q |= Q(rism_siglum__name__icontains=term) | Q(
                    rism_siglum__description__icontains=term
                )
                description_q |= Q(description__icontains=term)
                provenance_q |= Q(provenance__name__icontains=term)
            # All the Q objects are put together with OR.
            # The end result is that at least one term has to match in at least one
            # field
            general_search_q = (
                title_q | siglum_q | rism_siglum_q | description_q | provenance_q
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
                inventoried_by_q |= Q(invetoried_by__first_name__icontains=term) | Q(
                    invetoried_by__family_name__icontains=term
                )
                full_text_entered_by_q |= Q(
                    full_text_entered_by__first_name__icontains=term
                ) | Q(full_text_entered_by__family_name__icontains=term)
                melodies_entered_by_q |= Q(
                    melodies_entered_by__first_name__icontains=term
                ) | Q(melodies_entered_by__family_name__icontains=term)
                proofreaders_q |= Q(proofreaders__first_name__icontains=term) | Q(
                    proofreaders__family_name__icontains=term
                )
                other_editors_q |= Q(other_editors__first_name__icontains=term) | Q(
                    other_editors__family_name__icontains=term
                )
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

        return queryset.filter(q_obj_filter)
