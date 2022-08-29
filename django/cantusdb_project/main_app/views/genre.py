from typing import Dict, List

from django.views.generic import ListView
from django.views.generic.detail import SingleObjectMixin
from extra_views import SearchableListMixin
from main_app.models import Genre


class GenreDetailView(SingleObjectMixin, ListView):
    paginate_by = 100
    template_name = "genre_detail.html"

    def get_genre_cantus_ids(self, display_unpublished=True) -> List[Dict]:
        """
        Get a list with data on each unique ``cantus_id`` related to this Genre.

        The list contains dicts and each dict has the following keys:

        ``cantus_id``: The ``cantus_id``
        ``num_chants``: The number of Chants that have this ``cantus_id``
        ``first_incipit``: The incipit of first Chant with this ``cantus_id``
        ``first_incipit_url``: The url of first Chant with this ``cantus_id``

        Returns:
            List[Dict]: A list of dicts with data on each unique ``cantus_id``
        """
        cantus_ids = (self.object.chant_set
            .exclude(cantus_id=None)
            .values_list("cantus_id", flat=True)
            .distinct("cantus_id")
        )
        if not display_unpublished:
            cantus_ids = cantus_ids.filter(source__published=True)
        
        cantus_ids_list = list(cantus_ids)

        chant_list = []
        for cantus_id in cantus_ids_list:
            chants = self.object.chant_set.filter(cantus_id=cantus_id)
            num_chants = chants.count()
            first_chant = chants.first()
            first_incipit_url = first_chant.get_absolute_url()
            first_incipit = first_chant.incipit
            chant_list.append(
                {
                    "cantus_id": cantus_id,
                    "num_chants": num_chants,
                    "first_incipit": first_incipit,
                    "first_incipit_url": first_incipit_url,
                }
            )
        # Sort list based on number of Chants per cantus_id (descending)
        chant_list = sorted(chant_list, key=lambda k: k["num_chants"], reverse=True)
        return chant_list

    def get(self, request, *args, **kwargs):
        self.object = self.get_object(queryset=Genre.objects.all())
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["genre"] = self.object
        return context

    def get_queryset(self):
        display_unpublished = self.request.user.is_authenticated
        search_term = self.request.GET.get("incipit")
        if not search_term:
            return self.get_genre_cantus_ids(display_unpublished=display_unpublished)
        else:
            search_term = search_term.strip(" ")
            filtered_chants = [
                chant
                for chant in self.get_genre_cantus_ids(display_unpublished=display_unpublished)
                if search_term.lower() in chant["first_incipit"].lower()
            ]
            return filtered_chants


class GenreListView(SearchableListMixin, ListView):
    model = Genre
    paginate_by = 100
    context_object_name = "genres"
    template_name = "genre_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        mass_office = self.request.GET.get("mass_office", None)
        if mass_office in ["Mass", "Office", "Old Hispanic"]:
            queryset = queryset.filter(mass_office__contains=mass_office)
        return queryset.order_by("name")
