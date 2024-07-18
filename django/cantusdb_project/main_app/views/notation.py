from django.views.generic import DetailView
from main_app.models import Notation, Source


class NotationDetailView(DetailView):
    model = Notation
    context_object_name = "notation"
    template_name = "notation_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        notation = self.get_object()
        sources = Source.objects.filter(notation=notation).select_related(
            "holding_institution"
        )
        sources = sources.order_by("holding_institution__siglum", "shelfmark")
        context["sources"] = sources

        return context
