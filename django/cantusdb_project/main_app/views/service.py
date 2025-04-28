from django.views.generic import DetailView, ListView

from main_app.models import Service
from main_app.mixins import JSONResponseMixin


class ServiceDetailView(JSONResponseMixin, DetailView):  # type: ignore [type-arg]
    model = Service
    context_object_name = "service"
    template_name = "service_detail.html"
    json_fields = ["id", "name", "description"]


class ServiceListView(JSONResponseMixin, ListView):  # type: ignore [type-arg]
    model = Service
    queryset = Service.objects.order_by("name")
    paginate_by = 100
    context_object_name = "services"
    template_name = "service_list.html"
    json_fields = ["id", "name", "description"]
