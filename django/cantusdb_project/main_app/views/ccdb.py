from typing import Any, Optional

from django.conf import settings
from django.db.models import Q, QuerySet
from django.views.generic import TemplateView

from main_app.models import Chant, Source
from main_app.views.chant import ChantSearchView
from main_app.views.source import SourceListView

AVAILABLE_SEGMENTS = [
    (settings.CCDB_SEGMENT_ID, "Canadian Chant Database"),
    (settings.CANTUS_SEGMENT_ID, "Cantus Database"),
    (settings.BOWER_SEGMENT_ID, "Sequence Database"),
    (settings.CANTORALES_SEGMENT_ID, "Cantorales in the Americas and Beyond"),
]


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
    Chant search page scoped to the Canadian Chant Database by default.
    Users may expand the search to additional database segments via the 'db' GET param.
    Because ChantSearchView unions Chant and Sequence querysets before returning — and
    Django forbids filtering a unioned queryset — multi-segment support works by calling
    the parent's get_queryset() once per selected segment and unioning the results.
    """

    template_name = "ccdb_chant_search.html"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._current_segment_id: Optional[int] = None
        self._segment_ids: list[int] = []

    def _get_selected_segment_ids(self) -> list[int]:
        """Return the segment IDs selected via 'db' GET params. Defaults to CCDB segment."""
        raw = self.request.GET.getlist("db")
        ids = [int(v) for v in raw if str(v).isdigit()]
        return ids if ids else [settings.CCDB_SEGMENT_ID]

    def get_segment_id(self) -> Optional[str]:
        return str(self._current_segment_id) if self._current_segment_id is not None else None

    def get_queryset(self) -> QuerySet:
        if not self.request.GET:
            return Chant.objects.none()

        self._segment_ids = self._get_selected_segment_ids()

        if len(self._segment_ids) == 1:
            self._current_segment_id = self._segment_ids[0]
            return super().get_queryset()

        # Multi-segment: call the parent once per segment, then union the results.
        # We cannot filter after .union(), so segment injection happens via get_segment_id().
        querysets = []
        for seg_id in self._segment_ids:
            self._current_segment_id = seg_id
            querysets.append(super().get_queryset())
        self._current_segment_id = None

        combined = querysets[0]
        for qs in querysets[1:]:
            combined = combined.union(qs, all=True)
        return combined

    def get_context_data(self, **kwargs: Any) -> dict:
        context = super().get_context_data(**kwargs)
        # Use segment IDs cached by get_queryset; fall back to default on initial load
        segment_ids = self._segment_ids or [settings.CCDB_SEGMENT_ID]
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
