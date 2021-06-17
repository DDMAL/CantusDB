from django.views.generic import DetailView, ListView
from main_app.models import Sequence
from django.db.models import Q


class SequenceDetailView(DetailView):
    """
    Displays a single Sequence object. Accessed with ``sequences/<int:pk>``
    """

    model = Sequence
    context_object_name = "sequence"
    template_name = "sequence_detail.html"


class SequenceListView(ListView):
    """
    Displays a list of Sequence objects. Accessed with ``sequences/``
    """

    model = Sequence
    paginate_by = 100
    context_object_name = "sequences"
    template_name = "sequence_list.html"

    def get_queryset(self):
        queryset = super().get_queryset()
        q_obj_filter = Q(source__visible=True)
        q_obj_filter &= Q(source__public=True)
        return queryset.filter(q_obj_filter).order_by("siglum", "folio", "sequence")
