from typing import Any

from django.db.models import Q, QuerySet
from django.views.generic import TemplateView

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


AVAILABLE_SEGMENTS = [
    (4066, "Canadian Chant Database"),
    (4063, "Cantus Database"),
    (4064, "Sequence Database"),
    (4067, "Cantorales in the Americas and Beyond"),
]

_DEFAULT_SEGMENT_ID = 4066


class CcdbChantSearchView(CcdbMixin, ChantSearchView):
    """
    Chant search page scoped to the Canadian Chant Database (segment 4066) by default.
    Users may expand the search to additional database segments via the 'db' GET param.
    Because ChantSearchView unions Chant and Sequence querysets before returning — and
    Django forbids filtering a unioned queryset — multi-segment support works by calling
    the parent's get_queryset() once per selected segment and unioning the results.
    """

    template_name = "ccdb_chant_search.html"

    def _get_selected_segment_ids(self) -> list[int]:
        """Return the segment IDs selected via 'db' GET params. Defaults to [4066]."""
        raw = self.request.GET.getlist("db")
        ids = [int(v) for v in raw if str(v).isdigit()]
        return ids if ids else [_DEFAULT_SEGMENT_ID]

    def get_queryset(self) -> QuerySet:
        # If no search params, return empty queryset immediately (same as parent behaviour)
        if not self.request.GET:
            from main_app.models import Chant

            return Chant.objects.none()

        # Compute segment IDs before any GET manipulation so they survive the copy
        self._segment_ids = self._get_selected_segment_ids()

        # Make GET mutable
        self.request.GET = self.request.GET.copy()

        # Fast path: single segment — inject and delegate directly to parent
        if len(self._segment_ids) == 1:
            self.request.GET["segment"] = str(self._segment_ids[0])
            return super().get_queryset()

        # Multi-segment: call the parent once per segment, then union the results.
        # We cannot filter after .union(), so this is the only correct approach.
        base_get = self.request.GET.copy()
        base_get.pop("segment", None)

        querysets = []
        for seg_id in self._segment_ids:
            self.request.GET = base_get.copy()
            self.request.GET["segment"] = str(seg_id)
            querysets.append(super().get_queryset())

        # Restore GET (minus segment) so get_context_data reads clean params
        self.request.GET = base_get

        combined = querysets[0]
        for qs in querysets[1:]:
            combined = combined.union(qs, all=True)
        return combined

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)
        from main_app.models import Source

        # Use segment IDs cached by get_queryset; fall back to default on initial load
        segment_ids = getattr(self, "_segment_ids", [_DEFAULT_SEGMENT_ID])
        keyword = self.request.GET.get("keyword", "").strip()

        if keyword:
            source_qs = (
                Source.objects.filter(segment_m2m__id__in=segment_ids)
                .filter(
                    Q(shelfmark__unaccent__icontains=keyword)
                    | Q(holding_institution__siglum__unaccent__icontains=keyword)
                    | Q(description__unaccent__icontains=keyword)
                    | Q(summary__unaccent__icontains=keyword)
                    | Q(holding_institution__name__unaccent__icontains=keyword)
                    | Q(holding_institution__city__unaccent__icontains=keyword)
                    | Q(name__unaccent__icontains=keyword)
                )
                .distinct()
                .order_by("holding_institution__siglum", "shelfmark")
            )
        else:
            source_qs = Source.objects.none()

        context["ccdb_sources"] = source_qs
        context["ccdb_source_count"] = source_qs.count()
        context["selected_dbs"] = [str(i) for i in segment_ids]
        context["available_segments"] = AVAILABLE_SEGMENTS
        return context
