from django.views.generic import DetailView, ListView
from django.db.models import Q
from main_app.models import Source, Provenance, Century


class SourceDetailView(DetailView):
    model = Source
    context_object_name = "source"
    template_name = "source_detail.html"

    def get_context_data(self, **kwargs):
        object = self.get_object()
        context = super().get_context_data(**kwargs)
        if object.segment.id == 4064:
            # if this is a sequence source
            context["sequences"] = object.sequence_set.all().order_by("sequence")
            folios = (
                object.sequence_set.values_list("folio", flat=True)
                .distinct()
                .order_by("folio")
            )
        else:
            # if this is a normal chant source
            folios = (
                object.chant_set.values_list("folio", flat=True)
                .distinct()
                .order_by("folio")
            )
            # for the feast selector
            # feasts are aligned with the corresponding folios
            folios_with_feasts = []
            feasts_with_folios = []

            folios_with_feasts.append(folios[0])
            current_feast = (
                object.chant_set.filter(folio=folios[0])
                .exclude(feast=None)
                .order_by("sequence_number")
                .first()
                .feast
            )
            feasts_with_folios.append(current_feast)

            for folio in folios:
                chants_on_folio = object.chant_set.filter(folio=folio).order_by(
                    "sequence_number"
                )
                for chant in chants_on_folio:
                    if chant.feast != current_feast:
                        feasts_with_folios.append(chant.feast)
                        folios_with_feasts.append(folio)
                        current_feast = chant.feast

            feast_zip = zip(folios_with_feasts, feasts_with_folios)
            # the options for the feast selector on the right, only available for chants
            context["feasts_with_folios"] = feast_zip
        # the options for the folio selector on the right, for both chants and seqs
        context["folios"] = folios
        return context


class SourceListView(ListView):
    model = Source
    queryset = Source.objects.all().order_by("siglum")
    paginate_by = 1000
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
        # q_obj_filter = Q(visible_status="1")
        # q_obj_filter &= ~Q(source_status="Published / Proofread pending")
        # q_obj_filter &= ~Q(source_status="Unpublished / Proofread pending")
        # q_obj_filter &= ~Q(
        #     source_status="Editing process (not all the fields have been proofread)"
        # )
        q_obj_filter = Q(public=True)
        q_obj_filter &= Q(visible=True)

        if self.request.GET.get("century"):
            century_name = Century.objects.get(id=self.request.GET.get("century")).name
            q_obj_filter &= Q(century__name__icontains=century_name)

        if self.request.GET.get("provenance"):
            provenance_id = int(self.request.GET.get("provenance"))
            q_obj_filter &= Q(provenance__id=provenance_id)
        if self.request.GET.get("segment"):
            segment_id = int(self.request.GET.get("segment"))
            q_obj_filter &= Q(segment__id=segment_id)
        if self.request.GET.get("fullsource") in ["true", "false"]:
            full_source_str = self.request.GET.get("fullsource")
            if full_source_str == "true":
                full_source_q = Q(full_source=True) | Q(full_source=None)
                q_obj_filter &= full_source_q
            else:
                q_obj_filter &= Q(full_source=False)
        # Maybe change this to lookup in a search vector with the vector Postgres field?
        # I would have to add a signal to update the vector with changes like I did
        # with SIMSSADB
        if self.request.GET.get("general"):
            # Strip spaces at the beginning and end. Then make list of terms split on spaces
            general_search_terms = self.request.GET.get("general").strip(" ").split(" ")
            # We need a Q Object for each field we're gonna look into
            title_q = Q()
            siglum_q = Q()
            rism_siglum_q = Q()
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
                title_q |= Q(title__icontains=term)
                siglum_q |= Q(siglum__icontains=term)
                rism_siglum_q |= Q(rism_siglum__name__icontains=term) | Q(
                    rism_siglum__description__icontains=term
                )
                description_q |= Q(description__icontains=term)
                summary_q |= Q(summary__icontains=term)
                # provenance_q |= Q(provenance__name__icontains=term)
            # All the Q objects are put together with OR.
            # The end result is that at least one term has to match in at least one
            # field
            # general_search_q = (
            #     title_q | siglum_q | rism_siglum_q | description_q | provenance_q
            # )
            general_search_q = (
                title_q | siglum_q | rism_siglum_q | description_q | summary_q
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
                inventoried_by_q |= Q(inventoried_by__first_name__icontains=term) | Q(
                    inventoried_by__family_name__icontains=term
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

        return queryset.filter(q_obj_filter).distinct()
