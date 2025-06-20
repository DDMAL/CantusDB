from typing import Any

from django.views.generic import DetailView
from main_app.models import Century, Source
from main_app.permissions import CustomAccessMixin


class CenturyDetailView(CustomAccessMixin, DetailView):  # type: ignore[type-arg]
    model = Century
    context_object_name = "century"
    template_name = "century_detail.html"
    test_req = False

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        century = context["century"]
        if self.user.is_superuser or self.user_is_global_viewer:
            sources = Source.objects.all()
        else:
            sources = self.published_and_assigned_sources
        sources = sources.filter(century=century).select_related("holding_institution")
        sources = sources.order_by("holding_institution__name")

        context["sources"] = sources
        return context
