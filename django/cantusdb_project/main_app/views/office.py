from django.views.generic import DetailView, ListView

from main_app.models import Office


class OfficeDetailView(DetailView):
    model = Office
    context_object_name = "office"
    template_name = "office_detail.html"


class OfficeListView(ListView):
    model = Office
    queryset = Office.objects.order_by("name")
    paginate_by = 100
    context_object_name = "offices"
    template_name = "office_list.html"
