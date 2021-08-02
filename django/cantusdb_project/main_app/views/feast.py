from django.db.models import query
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
        ordering = self.request.GET.get("ordering")
        if ordering not in ["name", "feast_code"]:
            self.request.GET._mutable = True
            self.request.GET["ordering"] = "name"
            self.request.GET._mutable = False
            ordering = "name"
        return ordering

    def get_queryset(self):
        queryset = super().get_queryset()
        month = self.request.GET.get("month", None)
        date = self.request.GET.get("date")
        if date == "temp":
            queryset = queryset.filter(month=None, day=None)
        elif date == "sanc":
            queryset = queryset.exclude(month=None, day=None)

        if month and (int(month)) in range(1, 13):
            month = int(month)
            queryset = queryset.filter(month=month)
            return queryset
        else:
            return queryset
