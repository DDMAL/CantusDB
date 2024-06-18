from django.views.generic import DetailView
from main_app.models import Provenance, Source
from typing import Any


class ProvenanceDetailView(DetailView):
    model = Provenance
    context_object_name = "provenance"
    template_name = "provenance_detail.html"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        provenance = self.get_object()
        user = self.request.user
        display_unpublished = user.is_authenticated
        sources = Source.objects.filter(provenance=provenance)
        sources = sources.select_related("holding_institution",
                                         "provenance",
                                         "segment")

        if not display_unpublished:
            sources = sources.filter(published=True)

        sources = sources.order_by("holding_institution__name")

        context["sources"] = sources
        return context
