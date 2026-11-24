from typing import Any, Optional

from django.conf import settings
from django.db.models import Q
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.views.generic import TemplateView

from main_app.models import Source
from main_app.views.chant import ChantSearchView
from main_app.views.source import SourceListView


class CcdbMixin:
    """
    Adds ccdb_site=True to template context for all CCDB views.
    This allows the shared navbar to swap the Chant Search link to the
    CCDB-specific chant search page when browsing the Canadian Chant Database.
    """

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)  # type: ignore[misc]
        context["ccdb_site"] = True
        return context


class CcdbLandingView(CcdbMixin, SourceListView):
    """Landing page for the Canadian Chant Database."""

    pass


class CcdbTeamView(CcdbMixin, TemplateView):
    """Project Team page for the Canadian Chant Database."""

    template_name = "ccdb_team.html"


class CcdbMapView(CcdbMixin, TemplateView):
    """Map of Sources page for the Canadian Chant Database."""

    template_name = "ccdb_map.html"


class CcdbChantSearchView(CcdbMixin, ChantSearchView):
    """
    Chant search page of the Canadian Chant Database. It searches only the
    Canadian Chant Database's sources; the main chant search covers the other
    segments (#2359).
    """

    template_name = "ccdb_chant_search.html"

    def get_segment_id(self) -> Optional[str]:
        return str(settings.CCDB_SEGMENT_ID)

    def get(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        # Older links could search several databases, so a bookmarked page may
        # now be past the last page; send it to page 1 with the same search.
        try:
            return super().get(request, *args, **kwargs)
        except Http404:
            if "page" not in request.GET:
                raise
            params = request.GET.copy()
            del params["page"]
            return redirect(f"{request.path}?{params.urlencode()}")

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)
        keyword = self.request.GET.get("keyword", "").strip()

        if keyword:
            source_qs = (
                Source.objects.filter(segment_m2m__id=settings.CCDB_SEGMENT_ID)
                .filter(
                    Q(shelfmark__unaccent__icontains=keyword)
                    | Q(holding_institution__siglum__unaccent__icontains=keyword)
                    | Q(description__unaccent__icontains=keyword)
                    | Q(summary__unaccent__icontains=keyword)
                    | Q(holding_institution__name__unaccent__icontains=keyword)
                    | Q(holding_institution__city__unaccent__icontains=keyword)
                    | Q(name__unaccent__icontains=keyword)
                )
                .select_related("holding_institution", "provenance")
                .distinct()
                .order_by("holding_institution__siglum", "shelfmark")
            )
        else:
            source_qs = Source.objects.none()

        context["ccdb_sources"] = source_qs
        context["ccdb_source_count"] = source_qs.count()
        return context
