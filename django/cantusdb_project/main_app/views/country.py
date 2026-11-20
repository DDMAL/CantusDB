from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import DetailView

from main_app.data.countries_v2 import LEGACY_TO_POSITIVE
from main_app.models import Country


class CountryDetailView(DetailView):
    queryset = Country.objects.exclude(pk__in=(Country.UNKNOWN, Country.NOT_RECORDED))
    template_name = "country_detail.html"


def legacy_country_redirect(request, old_number):
    pk = LEGACY_TO_POSITIVE.get(-old_number)
    if pk is None or pk in (Country.UNKNOWN, Country.NOT_RECORDED):
        raise Http404
    return redirect("country-detail", pk=pk, permanent=True)
