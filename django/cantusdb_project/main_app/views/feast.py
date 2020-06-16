from django.views.generic import DetailView, ListView
from main_app.models import Feast
from extra_views import SearchableListMixin


class FeastDetailView(DetailView):
    model = Feast
    context_object_name = "feast"
    template_name = "feast_detail.html"


class FeastListView(SearchableListMixin, ListView):
    model = Feast
    queryset = Feast.objects.all()
    search_fields = ["name", "feast_code"]
    paginate_by = 200
    context_object_name = "feasts"
    template_name = "feast_list.html"

    def get_ordering(self):
        ordering = self.request.GET.get("ordering", "name")
        if ordering not in ["name", "feast_code"]:
            ordering = "name"
        return ordering

    def get_queryset(self):
        month = self.request.GET.get("month", None)
        if month and (int(month)) in range(1, 13):
            month = int(month)
            queryset = super().get_queryset().filter(month=month)
            return queryset
        else:
            return super().get_queryset()
