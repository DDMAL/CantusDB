from django.views.generic import DetailView

from main_app.models import Country


class CountryDetailView(DetailView):
    queryset = Country.objects.exclude(pk__in=(Country.UNKNOWN, Country.NOT_RECORDED))
    template_name = "country_detail.html"
