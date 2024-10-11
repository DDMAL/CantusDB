from django.views.generic import DetailView, ListView
from main_app.models import Genre
from main_app.mixins import JSONResponseMixin


class GenreDetailView(JSONResponseMixin, DetailView):
    model = Genre
    context_object_name = "genre"
    template_name = "genre_detail.html"
    json_fields = ["id", "name", "description", "mass_office"]


class GenreListView(JSONResponseMixin, ListView):
    model = Genre
    paginate_by = 100
    context_object_name = "genres"
    template_name = "genre_list.html"
    json_fields = ["id", "name", "description", "mass_office"]

    def get_queryset(self):
        queryset = super().get_queryset()
        mass_office = self.request.GET.get("mass_office", None)
        if mass_office in ["Mass", "Office", "Old Hispanic"]:
            queryset = queryset.filter(mass_office__contains=mass_office)
        return queryset.order_by("name")
