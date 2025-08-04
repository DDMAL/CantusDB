from typing import Any, Dict

from django.views.generic import DetailView
from main_app.models import Notation, Source
from main_app.permissions import CustomAccessMixin


class NotationDetailView(CustomAccessMixin, DetailView):  # type: ignore[type-arg]
    model = Notation
    context_object_name = "notation"
    template_name = "notation_detail.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        notation = self.get_object()
        if self.user.is_superuser or self.user_is_global_viewer:
            sources = Source.objects.all()
        else:
            sources = self.published_and_assigned_sources
        sources = sources.filter(notation=notation).select_related(
            "holding_institution"
        )
        sources = sources.order_by("holding_institution__siglum", "shelfmark")
        context["sources"] = sources

        return context
