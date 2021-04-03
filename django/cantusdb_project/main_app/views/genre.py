from typing import Dict, List

from django.views.generic import DetailView, ListView
from extra_views import SearchableListMixin
from main_app.models import Genre


class GenreDetailView(DetailView):
    model = Genre
    context_object_name = "genre"
    template_name = "genre_detail.html"

    def get_genre_cantus_ids(self) -> List[Dict]:
        """
        Get a list with data on each unique ``cantus_id`` related to this Genre.

        The list contains dicts and each dict has the following keys:

        ``"cantus_id"``: The ``cantus_id``
        ``"num_chants"``: The number of Chants that have this ``cantus_id``
        ``"first_incipit"``: The incipit of first Chant with this ``cantus_id``
        ``"first_incipit_url"``: The url of first Chant with this ``cantus_id``

        Returns:
            List[Dict]: A list of dicts with data on each unique ``cantus_id``
        """
        cantus_ids = list(
            self.object.chant_set.order_by("cantus_id")
            .exclude(cantus_id=None)
            .values_list("cantus_id", flat=True)
            .distinct("cantus_id")
        )

        chant_list = []
        for cantus_id in cantus_ids:
            chants = self.object.chant_set.filter(
                cantus_id=cantus_id
            ).order_by("id")
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
            chant_list = sorted(
                chant_list, key=lambda k: k["num_chants"], reverse=True
            )
        return chant_list

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add the list of cantus_ids to the context
        context["genre_chant_list"] = self.get_genre_cantus_ids()
        return context


class GenreListView(SearchableListMixin, ListView):
    model = Genre
    queryset = Genre.objects.all().order_by("name")
    search_fields = ["name"]
    paginate_by = 100
    context_object_name = "genres"
    template_name = "genre_list.html"

    def get_queryset(self):
        mass_office = self.request.GET.get("mass_office", None)
        if mass_office in ["Mass", "Office", "Old Hispanic"]:
            # Put mass_office in a list because the contains lookup requires one
            queryset = (
                super()
                .get_queryset()
                .filter(mass_office__contains=[mass_office])
            )
            return queryset
        return super().get_queryset()
