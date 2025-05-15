# main_app/views.py (or wherever your ProofreadView is)

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Q
from django.views.generic import ListView

from main_app.models import Source

CANTUS_SEGMENT_ID = 4063
BOWER_SEGMENT_ID = 4064


class ProofreadView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Source
    template_name = "proofreading_overview.html"
    context_object_name = "sources_to_proofread"
    paginate_by = 50

    def test_func(self):
        user = self.request.user
        if user.is_superuser:
            return True
        user_groups = user.groups.all().values_list("name", flat=True)
        is_project_manager = "project manager" in user_groups
        is_editor = "editor" in user_groups
        return is_project_manager or is_editor

    def get_queryset(self):
        user = self.request.user

        queryset = Source.objects.filter(
            Q(segment_m2m__id=CANTUS_SEGMENT_ID) & Q(number_of_chants__gt=0)
        ).select_related("proofreading_stats", "holding_institution")

        is_project_manager = user.groups.filter(name="project manager").exists()
        if not is_project_manager and user.groups.filter(name="editor").exists():
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

        # Sorting
        order_param = self.request.GET.get("order", "country")
        sort_param = self.request.GET.get("sort", "asc")
        sort_prefix = "-" if sort_param == "desc" else ""

        sort_mapping = {
            "country": [
                "holding_institution__country",
                "holding_institution__city",
                "holding_institution__name",
                "siglum",  # Source.siglum (RISM siglum + shelfmark)
            ],
            "city_institution": [
                "holding_institution__city",
                "holding_institution__name",
                "siglum",  # Source.siglum
            ],
            "source_siglum": ["siglum"],  # Source.siglum field
            "shelfmark": [
                "shelfmark",
                "holding_institution__siglum",
            ],  # Original shelfmark sort
            "published": ["published", "siglum"],  # Added siglum as tie-breaker
            "volpiano": ["proofreading_stats__num_volpiano_to_proofread", "siglum"],
            "ms_text": ["proofreading_stats__num_ms_full_text_to_proofread", "siglum"],
            "ms_text_std": [
                "proofreading_stats__num_ms_full_text_std_to_proofread",
                "siglum",
            ],
            "other": ["proofreading_stats__num_other_fields_to_proofread", "siglum"],
            "needing_proof": [
                "proofreading_stats__total_chants_needing_proofread",
                "siglum",
            ],
            "total_chants": ["proofreading_stats__total_chants_in_source", "siglum"],
            "percent_complete": ["proofreading_stats__percent_complete", "siglum"],
        }

        primary_sort_fields = sort_mapping.get(order_param, sort_mapping["country"])

        if not isinstance(primary_sort_fields, list):
            primary_sort_fields = [primary_sort_fields]

        ordering_fields = [f"{sort_prefix}{field}" for field in primary_sort_fields]

        # Fallback if somehow ordering_fields is empty (should not happen with default in .get)
        if not ordering_fields:
            ordering_fields = [
                f"{sort_prefix}holding_institution__country",
                f"{sort_prefix}siglum",
            ]

        return queryset.order_by(*ordering_fields)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_search_query"] = self.request.GET.get("q", "")
        context["current_order_param"] = self.request.GET.get(
            "order", "country"
        )  # Default to country
        context["current_sort_param"] = self.request.GET.get("sort", "asc")
        return context
