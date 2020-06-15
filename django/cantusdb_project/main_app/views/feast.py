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
    def get_ordering(self):
        ordering = self.request.GET.get("ordering", "name")
        if ordering not in ["name", "feast_code"]:
            ordering = "name"
        return ordering

