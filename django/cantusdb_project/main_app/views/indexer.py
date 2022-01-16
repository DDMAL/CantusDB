from django.db.models.aggregates import Count
from django.db.models.query_utils import Q
from django.views.generic import DetailView, ListView
from main_app.models import Indexer
from extra_views import SearchableListMixin
from django.db.models.functions import Lower


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
    search_fields = ["first_name", "family_name", "institution", "city", "country"]
    paginate_by = 100
    template_name = "indexer_list.html"
    context_object_name = "indexers"

    def get_queryset(self):
        # sources_inventoried is the related name for the Source model in its many-to-many relationship with the Indexer model
        queryset = (
            super()
            .get_queryset()
            .annotate(
                source_count=Count(
                    "sources_inventoried", filter=Q(sources_inventoried__public=True)
                )
            )
            .exclude(source_count=0)
            .order_by(Lower("family_name"))
        )
        return queryset
