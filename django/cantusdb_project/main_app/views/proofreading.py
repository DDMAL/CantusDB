import datetime

from django.conf import settings
from django.db.models import (
    Q,
    Count,
    F,
    ExpressionWrapper,
    FloatField,
    Case,
    When,
    Value,
)
from django.views.generic import ListView
from django.views.generic.list import MultipleObjectMixin
from django.utils import timezone

from main_app.models import Source
from main_app.permissions import CustomAccessMixin


class ProofreadView(CustomAccessMixin, ListView, MultipleObjectMixin):
    model = Source
    template_name = "proofreading_overview.html"
    context_object_name = "sources"
    paginate_by = 50

    def test_func(self):
        return self.user_is_editor

    def get_queryset(self):
        user = self.request.user

        queryset = Source.objects.filter(
            Q(segment_m2m__id=settings.CANTUS_SEGMENT_ID) & Q(number_of_chants__gt=0)
        ).select_related("holding_institution")

        if not user.is_superuser:
            queryset = queryset.filter(
                id__in=user.sources_user_can_edit.values_list("id", flat=True)
            )

        search_query = self.request.GET.get("q", "").strip()
        if search_query:
            search_filter = (
                Q(holding_institution__siglum__icontains=search_query)
                | Q(shelfmark__icontains=search_query)
                | Q(holding_institution__name__icontains=search_query)
                | Q(holding_institution__city__icontains=search_query)
                | Q(holding_institution__country__icontains=search_query)
                | Q(title__icontains=search_query)
                | Q(siglum__icontains=search_query)
            )
            queryset = queryset.filter(search_filter)

        # Inactive Source Filtering
        inactive_filter = self.request.GET.get("inactive", None)
        if inactive_filter:
            today = timezone.now()
            if inactive_filter == "3":
                cutoff_date = today - datetime.timedelta(days=90)
            elif inactive_filter == "6":
                cutoff_date = today - datetime.timedelta(days=180)
            elif inactive_filter == "12":
                cutoff_date = today - datetime.timedelta(days=365)
            else:
                cutoff_date = None

            if cutoff_date:
                queryset = queryset.filter(
                    Q(date_created__lt=cutoff_date, last_updated_by__isnull=True)
                    | Q(last_updated_by__isnull=False, date_updated__lt=cutoff_date)
                )

        # Annotate queryset with calculated statistics
        # Counts for items TO proofread (referencing fields on the related Chant model)
        queryset = queryset.annotate(
            num_volpiano_to_proofread=Count(
                "chant",
                filter=Q(chant__volpiano__isnull=False, chant__volpiano__gt="")
                & ~Q(chant__volpiano_proofread=True),
                distinct=True,
            ),
            num_ms_full_text_to_proofread=Count(
                "chant",
                filter=Q(
                    chant__manuscript_full_text__isnull=False,
                    chant__manuscript_full_text__gt="",
                )
                & ~Q(chant__manuscript_full_text_proofread=True),
                distinct=True,
            ),
            num_ms_full_text_std_to_proofread=Count(
                "chant",
                filter=Q(
                    chant__manuscript_full_text_std_spelling__isnull=False,
                    chant__manuscript_full_text_std_spelling__gt="",
                )
                & ~Q(chant__manuscript_full_text_std_proofread=True),
                distinct=True,
            ),
            num_other_fields_to_proofread=Count(
                "chant", filter=Q(chant__other_fields_proofread=False), distinct=True
            ),
            # Total chants needing proofread (at least one field)
            total_chants_needing_proofread=Count(
                "chant",
                filter=(
                    (
                        Q(chant__volpiano__isnull=False, chant__volpiano__gt="")
                        & ~Q(chant__volpiano_proofread=True)
                    )
                    | (
                        Q(
                            chant__manuscript_full_text__isnull=False,
                            chant__manuscript_full_text__gt="",
                        )
                        & ~Q(chant__manuscript_full_text_proofread=True)
                    )
                    | (
                        Q(
                            chant__manuscript_full_text_std_spelling__isnull=False,
                            chant__manuscript_full_text_std_spelling__gt="",
                        )
                        & ~Q(chant__manuscript_full_text_std_proofread=True)
                    )
                    | (Q(chant__other_fields_proofread=False))
                ),
                distinct=True,
            ),
            # Counts for items that ARE proofread (for percent_complete)
            num_volpiano_is_proofread=Count(
                "chant",
                filter=Q(chant__volpiano__isnull=False, chant__volpiano__gt="")
                & Q(chant__volpiano_proofread=True),
                distinct=True,
            ),
            num_ms_full_text_is_proofread=Count(
                "chant",
                filter=Q(
                    chant__manuscript_full_text__isnull=False,
                    chant__manuscript_full_text__gt="",
                )
                & Q(chant__manuscript_full_text_proofread=True),
                distinct=True,
            ),
            num_ms_full_text_std_is_proofread=Count(
                "chant",
                filter=Q(
                    chant__manuscript_full_text_std_spelling__isnull=False,
                    chant__manuscript_full_text_std_spelling__gt="",
                )
                & Q(chant__manuscript_full_text_std_proofread=True),
                distinct=True,
            ),
            num_other_fields_is_proofread=Count(
                "chant",
                filter=Q(chant__other_fields_proofread=True),
                distinct=True,
            ),
            # Counts for "opportunities" (for percent_complete)
            volpiano_opportunities=Count(
                "chant",
                filter=Q(chant__volpiano__isnull=False, chant__volpiano__gt=""),
                distinct=True,
            ),
            ms_full_text_opportunities=Count(
                "chant",
                filter=Q(
                    chant__manuscript_full_text__isnull=False,
                    chant__manuscript_full_text__gt="",
                ),
                distinct=True,
            ),
            ms_full_text_std_opportunities=Count(
                "chant",
                filter=Q(
                    chant__manuscript_full_text_std_spelling__isnull=False,
                    chant__manuscript_full_text_std_spelling__gt="",
                ),
                distinct=True,
            ),
            # other_fields_opportunities is equivalent to total_chants_in_source (now Source.number_of_chants)
        )

        # Calculate sums for percent_complete using F objects
        total_individual_fields_actually_proofread_expr = (
            F("num_volpiano_is_proofread")
            + F("num_ms_full_text_is_proofread")
            + F("num_ms_full_text_std_is_proofread")
            + F("num_other_fields_is_proofread")
        )
        total_proofread_opportunities_expr = (
            F("volpiano_opportunities")
            + F("ms_full_text_opportunities")
            + F("ms_full_text_std_opportunities")
            + F("number_of_chants")  # 'other_fields' opportunities are total chants
        )

        queryset = queryset.annotate(
            total_individual_fields_actually_proofread=total_individual_fields_actually_proofread_expr,
            total_proofread_opportunities=total_proofread_opportunities_expr,
        ).annotate(
            percent_complete=Case(
                When(total_proofread_opportunities=0, then=Value(100.0)),
                default=ExpressionWrapper(
                    (100.0 * F("total_individual_fields_actually_proofread"))
                    / F("total_proofread_opportunities"),
                    output_field=FloatField(),
                ),
                output_field=FloatField(),
            )
        )

        if inactive_filter == "proofread_unpublished":
            queryset = queryset.filter(
                published=False, total_chants_needing_proofread=0
            )

        # Sorting
        order_param = self.request.GET.get("order", "country")
        sort_param = self.request.GET.get("sort", "asc")
        sort_prefix = "-" if sort_param == "desc" else ""

        if order_param == "country":
            # Mirror Browse Sources: order private collectors (whose siglum is
            # NULL) after institutions with sigla within the same country group.
            # PostgreSQL's native default already does this: NULLS LAST for
            # ascending, NULLS FIRST for descending, which matches the Python
            # sort used in tests (`(siglum is None, siglum or "")`) once the
            # whole list is reversed for a descending sort. A final `id`
            # tiebreaker keeps ordering deterministic.
            ordering_fields = [
                f"{sort_prefix}holding_institution__country",
                f"{sort_prefix}holding_institution__siglum",
                f"{sort_prefix}shelfmark",
                f"{sort_prefix}id",
            ]
            return queryset.order_by(*ordering_fields)

        # Updated sort_mapping to use annotated fields
        sort_mapping = {
            "city_institution": [
                "holding_institution__city",
                "holding_institution__name",
                "holding_institution__siglum",
                "shelfmark",
            ],
            "source_siglum": ["holding_institution__siglum", "shelfmark"],
            "shelfmark": [
                "shelfmark",
                "holding_institution__siglum",
            ],
            "published": ["published", "holding_institution__siglum", "shelfmark"],
            "volpiano": [
                "num_volpiano_to_proofread",
                "holding_institution__siglum",
                "shelfmark",
            ],
            "ms_text": [
                "num_ms_full_text_to_proofread",
                "holding_institution__siglum",
                "shelfmark",
            ],
            "ms_text_std": [
                "num_ms_full_text_std_to_proofread",
                "holding_institution__siglum",
                "shelfmark",
            ],
            "other": [
                "num_other_fields_to_proofread",
                "holding_institution__siglum",
                "shelfmark",
            ],
            "needing_proof": [
                "total_chants_needing_proofread",
                "holding_institution__siglum",
                "shelfmark",
            ],
            "total_chants": [
                "number_of_chants",
                "holding_institution__siglum",
                "shelfmark",
            ],
            "percent_complete": [
                "percent_complete",
                "holding_institution__siglum",
                "shelfmark",
            ],
        }

        primary_sort_fields = sort_mapping.get(order_param, [])

        if not isinstance(primary_sort_fields, list):
            primary_sort_fields = [primary_sort_fields]

        ordering_fields = [f"{sort_prefix}{field}" for field in primary_sort_fields]

        # An unrecognized `order` yields no mapped fields; fall back to the same
        # ordering as the default "country" branch. The `id` tiebreaker keeps it
        # a total order so pagination stays consistent.
        if not ordering_fields:
            ordering_fields = [
                f"{sort_prefix}holding_institution__country",
                f"{sort_prefix}holding_institution__siglum",
                f"{sort_prefix}shelfmark",
                f"{sort_prefix}id",
            ]

        return queryset.order_by(*ordering_fields)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Proofreading Overview"
        context["current_search_query"] = self.request.GET.get("q", "")
        context["current_order_param"] = self.request.GET.get(
            "order", "country"
        )  # Default to country
        context["current_sort_param"] = self.request.GET.get("sort", "asc")
        context["current_inactive_filter"] = self.request.GET.get("inactive", None)

        return context
