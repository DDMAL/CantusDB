from django.views.generic import DetailView, ListView
from django.db.models import QuerySet
from main_app.models import Genre  # type: ignore[attr-defined]
from main_app.mixins import JSONResponseMixin


class GenreDetailView(JSONResponseMixin, DetailView):  # type: ignore[type-arg]
    model = Genre
    context_object_name = "genre"
    template_name = "genre_detail.html"
    json_fields = ["id", "name", "description", "mass_office"]


class GenreListView(JSONResponseMixin, ListView):  # type: ignore[type-arg]
    model = Genre
    paginate_by = 100
    context_object_name = "genres"
    template_name = "genre_list.html"
    json_fields = ["id", "name", "description", "mass_office"]

    def get_queryset(self) -> QuerySet[Genre]:
        order_attr = self.request.GET.get("order", "name")
        sort_attr = self.request.GET.get("sort", "asc")
        return Genre.objects.all().order_by(
            order_attr if sort_attr == "asc" else f"-{order_attr}"
        )
