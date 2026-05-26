from django.views.generic import DetailView, ListView
from django.db.models import QuerySet
from django.db.models.functions import Lower
from main_app.models import Genre
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
        # genres can be ordered by name or description,
        # default to ordering by name if given anything else
        if order_attr not in ["name", "description"]:
            order_attr = "name"
        sort_attr = self.request.GET.get("sort", "asc")
        ordering = Lower(order_attr)
        return Genre.objects.all().order_by(
            ordering if sort_attr == "asc" else ordering.desc()
        )
