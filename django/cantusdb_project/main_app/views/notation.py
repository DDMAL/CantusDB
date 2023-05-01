from django.views.generic import DetailView
from main_app.models import Notation


class NotationDetailView(DetailView):
    model = Notation
    context_object_name = "notation"
    template_name = "notation_detail.html"
