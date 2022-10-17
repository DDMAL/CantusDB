from django.views.generic import DetailView
from main_app.models import Provenance

class ProvenanceDetailView(DetailView):
    model = Provenance
    context_object_name = "provenance"
    template_name = "provenance_detail.html"
