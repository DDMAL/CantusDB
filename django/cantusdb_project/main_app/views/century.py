from django.views.generic import DetailView
from main_app.models import Century, Source
from typing import Any, Dict

class CenturyDetailView(DetailView):
    model = Century
    context_object_name = "century"
    template_name = "century_detail.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        context = super().get_context_data(**kwargs)
        century = self.get_object()
        user = self.request.user
        display_unpublished = user.is_authenticated
        print(display_unpublished)
        sources = Source.objects.filter(century=century)
        if not display_unpublished:
            print("filtering chants!    ")
            sources = sources.filter(published=True)
        context["sources"] = sources
        return context