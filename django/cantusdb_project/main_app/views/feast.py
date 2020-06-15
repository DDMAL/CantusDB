from django.views.generic import DetailView, ListView
from main_app.models import Feast


class FeastDetailView(DetailView):
    model = Feast
    context_object_name = "feast"
    template_name = "feast_detail.html"


class FeastListView(ListView):
    model = Feast
    queryset = Feast.objects.order_by("name")
    paginate_by = 100
    template_name = "list.html"
