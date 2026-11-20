from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import DetailView

from main_app.models import Country


class CountryDetailView(DetailView):
    queryset = Country.objects.exclude(pk__in=(Country.UNKNOWN, Country.NOT_RECORDED))
    template_name = "country_detail.html"


def legacy_country_redirect(request, old_number):
    # The original public catalogue URLs ran from -101 through -136.
    if not 101 <= old_number <= 136:
        raise Http404
    return redirect("country-detail", pk=old_number - 100, permanent=True)
