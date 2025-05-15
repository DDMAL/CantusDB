from django.contrib import admin
from main_app.models import ProofreadingStats


@admin.register(ProofreadingStats)
class ProofreadingStatsAdmin(admin.ModelAdmin):
    list_display = (
        "source",
        "total_chants_in_source",
        "total_chants_needing_proofread",
        "total_proofread_opportunities",
        "total_individual_fields_to_proofread",
        "percent_complete",
        "updated_at",
    )
    readonly_fields = (
        "source",
        "num_volpiano_to_proofread",
        "num_ms_full_text_to_proofread",
        "num_ms_full_text_std_to_proofread",
        "num_other_fields_to_proofread",
        "total_chants_in_source",
        "total_chants_needing_proofread",
        "total_proofread_opportunities",
        "total_individual_fields_to_proofread",
        "percent_complete",
        "updated_at",
    )
    search_fields = (
        "source__id",
        "source__title",
    )  # Assuming your Source model has a 'title' field for its name. Adjust if it's different (e.g., 'name').
