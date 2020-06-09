from django.views.generic import DetailView, ListView
from main_app.models import Indexer
from extra_views import SearchableListMixin

class IndexerDetailView(DetailView):
    model = Indexer
    context_object_name = "indexer"
    template_name = "indexer_detail.html"


class IndexerListView(SearchableListMixin, ListView):
    model = Indexer
    queryset = Indexer.objects.order_by("first_name")
    template_name = "indexer_list.html"
    context_object_name = "indexers"
