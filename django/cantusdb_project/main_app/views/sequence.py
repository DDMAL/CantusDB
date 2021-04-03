from django.views.generic import DetailView, ListView
from main_app.models import Sequence


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
    queryset = Sequence.objects.all().order_by("id")
    paginate_by = 100
    context_object_name = "sequences"
    template_name = "sequence_list.html"
