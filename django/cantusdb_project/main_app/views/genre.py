from django.views.generic import DetailView, ListView
from main_app.models import Genre
from extra_views import SearchableListMixin


class GenreDetailView(DetailView):
    model = Genre
    context_object_name = "genre"
    template_name = "genre_detail.html"


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
                super().get_queryset().filter(mass_office__contains=[mass_office])
            )
            return queryset
        else:
            return super().get_queryset()
