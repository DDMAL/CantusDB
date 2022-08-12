from django.views.generic import DetailView, ListView, CreateView, UpdateView
from django.db.models import Q
from main_app.models import Source, Provenance, Century, Chant
from main_app.forms import SourceCreateForm, SourceEditForm
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404


class SourceDetailView(DetailView):
    model = Source
    context_object_name = "source"
    template_name = "source_detail.html"

    def get_context_data(self, **kwargs):
        def get_feast_selector_options(source, folios):
            """Generate folio-feast pairs as options for the feast selector

            Going through all chants in the source, folio by folio,
            a new entry (in the form of folio-feast) is added when the feast changes. 

            Args:
                source (Source object): The source object for this source detail page.
                folios (list of strs): A list of folios in the source.

            Returns:
                list of tuples: A list of folios and Feast objects, to be unpacked in template.
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
                # if none of the chants in this source has a feast, return an empty list
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

        source = self.get_object()
        if (source.published is False) and (not self.request.user.is_authenticated):
            raise PermissionDenied()

        context = super().get_context_data(**kwargs)

        if source.segment and source.segment.id == 4064:
            # if this is a sequence source
            context["sequences"] = source.sequence_set.all().order_by("sequence")
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
            context["feasts_with_folios"] = get_feast_selector_options(source, folios)
        return context



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
                inventoried_by_q |= Q(inventoried_by__given_name__icontains=term) | Q(
                    inventoried_by__family_name__icontains=term
                )
                full_text_entered_by_q |= Q(
                    full_text_entered_by__given_name__icontains=term
                ) | Q(full_text_entered_by__family_name__icontains=term)
                melodies_entered_by_q |= Q(
                    melodies_entered_by__given_name__icontains=term
                ) | Q(melodies_entered_by__family_name__icontains=term)
                proofreaders_q |= Q(proofreaders__given_name__icontains=term) | Q(
                    proofreaders__family_name__icontains=term
                )
                other_editors_q |= Q(other_editors__given_name__icontains=term) | Q(
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

class SourceCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Source
    template_name = "source_create_form.html"
    form_class = SourceCreateForm

    def test_func(self):
        user = self.request.user
        # checks if the user is allowed to create sources
        is_authorized = user.groups.filter(Q(name="project manager")|Q(name="editor")|Q(name="contributor")).exists()

        if is_authorized:
            return True
        else:
            return False

    def get_success_url(self):
        return reverse("source-create")

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        source = form.save()

        # assign this source to the "current_editors"
        current_editors = source.current_editors.all()
        
        for editor in current_editors:
            editor.sources_user_can_edit.add(source)
        
        messages.success(
            self.request,
            "Source created successfully!",
        )
        
        return HttpResponseRedirect(self.get_success_url())

class SourceEditView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    template_name = "source_edit.html"
    model = Source
    form_class = SourceEditForm 
    pk_url_kwarg = "source_id"

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
            or (is_contributor and source.created_by == user)):
            return True
        else:
            return False

    def form_valid(self, form):
        form.instance.last_updated_by = self.request.user

        # remove this source from the old "current_editors"
        # assign this source to the new "current_editors"

        old_current_editors = list(Source.objects.get(id=form.instance.id).current_editors.all())
        new_current_editors = form.cleaned_data["current_editors"]
        source = form.save()

        for old_editor in old_current_editors:
            old_editor.sources_user_can_edit.remove(source)
        
        for new_editor in new_current_editors:
            new_editor.sources_user_can_edit.add(source)
        
        return HttpResponseRedirect(self.get_success_url())
