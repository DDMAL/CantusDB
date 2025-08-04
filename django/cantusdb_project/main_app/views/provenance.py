from typing import Any, Dict
from django.views.generic import DetailView
from main_app.models import Provenance, Source
from main_app.permissions import CustomAccessMixin


class ProvenanceDetailView(CustomAccessMixin, DetailView):  # type: ignore[type-arg]
    model = Provenance
    context_object_name = "provenance"
    template_name = "provenance_detail.html"
    test_req = False

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        provenance = context["provenance"]
        if self.user.is_superuser or self.user_is_global_viewer:
            sources = Source.objects.all()
        else:
            sources = self.published_and_assigned_sources
        sources = sources.filter(provenance=provenance)
        sources = sources.select_related(
            "holding_institution", "provenance"
        ).prefetch_related("segment_m2m")

        sources = sources.order_by("holding_institution__name")

        context["sources"] = sources
        return context
