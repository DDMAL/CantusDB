from django.views.generic import DetailView, ListView
from extra_views import SearchableListMixin
from main_app.models import Genre


class GenreDetailView(DetailView):
    model = Genre
    context_object_name = "genre"
    template_name = "genre_detail.html"


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
