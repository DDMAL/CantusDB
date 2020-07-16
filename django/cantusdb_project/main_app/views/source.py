from django.views.generic import DetailView, ListView
from main_app.models import Source
from extra_views import SearchableListMixin


class SourceDetailView(DetailView):
    model = Source
    context_object_name = "source"
    template_name = "source_detail.html"


class SourceListView(SearchableListMixin, ListView):
    model = Source
    queryset = Source.objects.all().order_by("siglum")
    search_fields = ["name"]
    paginate_by = 100
    context_object_name = "sources"
    template_name = "source_list.html"
