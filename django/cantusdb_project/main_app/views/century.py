from django.views.generic import DetailView
from main_app.models import Century

class CenturyDetailView(DetailView):
    model = Century
    context_object_name = "century"
    template_name = "century_detail.html"
