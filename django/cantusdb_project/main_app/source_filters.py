"""
Filters on a source's own fields: the country of its holding institution,
its provenance, date range, physical status and production method.

Browse Sources filters sources with them, and chant search filters chants and
sequences by their source (#2354), so both pages offer the same filters.
"""

from datetime import date
from functools import cached_property
from typing import Any, Optional, TypeVar

from django.db.models import Max, Min, Model, Q, QuerySet
from django.http import HttpRequest

from main_app.models import Century, Institution, Provenance, Source

# GET params of the source filters that are empty unless the user set them.
SOURCE_FILTER_FIELDS: tuple[str, ...] = ("country", "provenance", "prodMethod")

M = TypeVar("M", bound=Model)


class SourceFilterMixin:
    """Source filters for a view: query, active state and the form's options."""

    request: HttpRequest

    @cached_property
    def date_range_bounds(self) -> tuple[Optional[int], Optional[int]]:
        """
        Year-range slider bounds. Endpoints are rounded out to the nearest
        multiple of 5 so the slider's step="5" reaches both. The upper bound
        is clipped to the current multiple of 5 so future-dated centuries
        (e.g. a "21st century" stub ending in 2099) do not stretch the
        slider past today.
        """
        current_year_rounded = (date.today().year // 5) * 5
        century_dates = Century.objects.filter(
            min_date__isnull=False, max_date__isnull=False
        ).aggregate(
            min_year=Min("min_date"),
            max_year=Max("max_date"),
        )
        min_year = century_dates["min_year"]
        max_year = century_dates["max_year"]
        date_range_min = (min_year // 5) * 5 if min_year is not None else None
        date_range_max = (
            min(-(-max_year // 5) * 5, current_year_rounded)
            if max_year is not None
            else None
        )
        return date_range_min, date_range_max

    @cached_property
    def requested_date_range(self) -> tuple[Optional[int], Optional[int]]:
        """
        The dateStart/dateEnd query parameters parsed to ints. A missing or
        non-numeric value becomes None rather than raising, so a mangled
        querystring can't break the page.
        """

        def parse(param: str) -> Optional[int]:
            raw = self.request.GET.get(param)
            if not raw:
                return None
            try:
                return int(raw)
            except (TypeError, ValueError):
                return None

        return parse("dateStart"), parse("dateEnd")

    @cached_property
    def date_range_active(self) -> bool:
        """
        True only when the requested range actually narrows the full range of
        dated sources (a bound sits strictly inside the outer bounds). When
        the slider is untouched the form still submits the outer bounds, so
        comparing against them keeps us from applying a century filter the
        user never asked for -- which would silently drop every source that
        has no century assigned. The numeric comparison also shrugs off
        differently-formatted or hand-edited querystrings.
        """
        date_range_min, date_range_max = self.date_range_bounds
        requested_start, requested_end = self.requested_date_range
        narrows_start = (
            requested_start is not None
            and date_range_min is not None
            and requested_start > date_range_min
        )
        narrows_end = (
            requested_end is not None
            and date_range_max is not None
            and requested_end < date_range_max
        )
        return narrows_start or narrows_end

    @cached_property
    def source_completeness_active(self) -> bool:
        """
        True when some physical status boxes are unticked. The form submits
        every box when none is changed, which filters nothing.
        """
        selected = set(self.request.GET.getlist("sourceCompleteness"))
        all_values = {
            str(value) for value, _ in Source.SourceCompletenessChoices.choices
        }
        return bool(selected) and selected != all_values

    @cached_property
    def source_filters_active(self) -> bool:
        return (
            any(self.request.GET.get(field) for field in SOURCE_FILTER_FIELDS)
            or self.date_range_active
            or self.source_completeness_active
        )

    def source_filters_q(self) -> Q:
        """The source filters set in the request, as a Q on Source."""
        q_obj_filter = Q()
        if country_name := self.request.GET.get("country"):
            q_obj_filter &= Q(holding_institution__country__icontains=country_name)

        # Keep only sources with a century that overlaps the range. This is
        # skipped when the range still spans the full extent of dated sources
        # -- see date_range_active -- so leaving the slider untouched does not
        # drop sources that simply have no century assigned.
        if self.date_range_active:
            date_start_int, date_end_int = self.requested_date_range
            if date_start_int is not None and date_end_int is not None:
                # Both dates specified: find centuries that overlap the range
                q_obj_filter &= Q(
                    century__min_date__lte=date_end_int,
                    century__max_date__gte=date_start_int,
                )
            elif date_start_int is not None:
                # Only start date: find centuries that haven't ended
                q_obj_filter &= Q(century__max_date__gte=date_start_int)
            elif date_end_int is not None:
                # Only end date: find centuries that have started
                q_obj_filter &= Q(century__min_date__lte=date_end_int)

        # Ignore an id that isn't a number, e.g. from an edited URL (#1484).
        if (provenance_id := self.request.GET.get("provenance", "")).isdigit():
            q_obj_filter &= Q(provenance__id=int(provenance_id))
        if self.source_completeness_active:
            q_obj_filter &= Q(
                source_completeness__in=self.request.GET.getlist("sourceCompleteness")
            )
        if production_method := self.request.GET.get("prodMethod"):
            q_obj_filter &= Q(production_method=production_method)
        return q_obj_filter

    def filter_by_source(self, queryset: QuerySet[M]) -> QuerySet[M]:
        """Keep the chants or sequences whose source matches the source filters.

        A subquery on Source rather than a join, so a source matching through
        several centuries doesn't repeat its chants.
        """
        if not (q_obj_filter := self.source_filters_q()):
            return queryset
        return queryset.filter(
            source_id__in=Source.objects.filter(q_obj_filter).values("id")
        )

    def source_filter_context(self) -> dict[str, Any]:
        """The options the source filter fields offer."""
        date_range_min, date_range_max = self.date_range_bounds
        return {
            "countries": Institution.objects.values_list("country", flat=True)
            .distinct()
            .order_by("country"),
            "provenances": Provenance.objects.all()
            .order_by("name")
            .values("id", "name"),
            "date_range_min": date_range_min,
            "date_range_max": date_range_max,
            "production_method_choices": Source.ProductionMethodChoices.choices,
            "source_completeness_choices": Source.SourceCompletenessChoices.choices,
        }
