from django.views.generic import DetailView, ListView
from main_app.models import Indexer
from extra_views import SearchableListMixin


class IndexerDetailView(DetailView):
    """Detail view for Indexer model

    Accessed by /indexers/<pk>
    """
    model = Indexer
    context_object_name = "indexer"
    template_name = "indexer_detail.html"


class IndexerListView(SearchableListMixin, ListView):
    """Searchable List view for Indexer model

    Accessed by /indexers/

    When passed a ``?q=<query>`` argument in the GET request, it will filter indexers
    based on the fields defined in ``search_fields`` with the ``icontains`` lookup
    """
    model = Indexer
    queryset = Indexer.objects.order_by("family_name")
    search_fields = ["first_name", "family_name", "institution", "city", "country"]
    paginate_by = 100
    template_name = "indexer_list.html"
    context_object_name = "indexers"
