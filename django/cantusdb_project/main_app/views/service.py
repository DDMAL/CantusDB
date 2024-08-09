from django.views.generic import DetailView, ListView

from main_app.models import Service


class ServiceDetailView(DetailView):
    model = Service
    context_object_name = "service"
    template_name = "service_detail.html"


class ServiceListView(ListView):
    model = Service
    queryset = Service.objects.order_by("name")
    paginate_by = 100
    context_object_name = "services"
    template_name = "service_list.html"
