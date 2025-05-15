from django.db import models
from django.db.models import Count, Q  # Ensure Count and Q are imported
from main_app.models import Chant, Source
from typing import Any

# PROOFREADING_CHANTS_Q:
# This dictionary defines Q objects used to identify specific fields within Chant objects
# that are populated (not null or empty) AND are NOT YET proofread.
# Each key corresponds to a proofreadable aspect of a Chant..
PROOFREADING_CHANTS_Q = {
    "volpiano": Q(volpiano__isnull=False, volpiano__gt="")
    & ~Q(volpiano_proofread="True"),
    "ms_full_text": Q(manuscript_full_text__isnull=False, manuscript_full_text__gt="")
    & ~Q(manuscript_full_text_proofread="True"),
    "ms_full_text_std": Q(
        manuscript_full_text_std_spelling__isnull=False,
        manuscript_full_text_std_spelling__gt="",
    )
    & ~Q(manuscript_full_text_std_proofread="True"),
    "other_fields": Q(
        other_fields_proofread=False
    ),  # 'other_fields' refers to a general proofreading status for the chant
}

# PROOFREADING_CHANTS_ARE_PROOFREAD_Q:
# This dictionary defines Q objects used to identify specific fields within Chant objects
# that are populated (not null or empty) AND HAVE BEEN proofread.
# Each key corresponds to a proofreadable aspect of a Chant.
# Counts how many of each field type have already been proofread for a given Source,
# contributing to the `total_individual_fields_actually_proofread` calculation for `percent_complete`.
PROOFREADING_CHANTS_ARE_PROOFREAD_Q = {
    "volpiano": Q(volpiano__isnull=False, volpiano__gt="") & Q(volpiano_proofread=True),
    "ms_full_text": Q(manuscript_full_text__isnull=False, manuscript_full_text__gt="")
    & Q(manuscript_full_text_proofread=True),
    "ms_full_text_std": Q(
        manuscript_full_text_std_spelling__isnull=False,
        manuscript_full_text_std_spelling__gt="",
    )
    & Q(manuscript_full_text_std_proofread=True),
    "other_fields": Q(
        other_fields_proofread=True
    ),  # 'other_fields' refers to a general proofreading status for the chant
}

# PROOFREADING_NEEDS_PROOFREAD_Q:
# This Q object combines all conditions from PROOFREADING_CHANTS_Q using an OR operator.
# It is used to identify any Chant that has at least one field requiring proofreading.
# Used to calculate `total_chants_needing_proofread` for a given Source.
PROOFREADING_NEEDS_PROOFREAD_Q = (
    PROOFREADING_CHANTS_Q["volpiano"]
    | PROOFREADING_CHANTS_Q["ms_full_text"]
    | PROOFREADING_CHANTS_Q["ms_full_text_std"]
    | PROOFREADING_CHANTS_Q["other_fields"]
)


class ProofreadingStatsManager(models.Manager):
    def calculate_and_update_for_source(self, source_obj) -> tuple[Any, bool]:

        # Aggregate counts for items TO proofread
        to_proofread_agg = Chant.objects.filter(source=source_obj).aggregate(
            num_volpiano_to_proofread=Count(
                "id", filter=PROOFREADING_CHANTS_Q["volpiano"]
            ),
            num_ms_full_text_to_proofread=Count(
                "id", filter=PROOFREADING_CHANTS_Q["ms_full_text"]
            ),
            num_ms_full_text_std_to_proofread=Count(
                "id", filter=PROOFREADING_CHANTS_Q["ms_full_text_std"]
            ),
            num_other_fields_to_proofread=Count(
                "id", filter=PROOFREADING_CHANTS_Q["other_fields"]
            ),
        )

        # Aggregate counts for items that ARE proofread
        are_proofread_agg = Chant.objects.filter(source=source_obj).aggregate(
            num_volpiano_is_proofread=Count(
                "id", filter=PROOFREADING_CHANTS_ARE_PROOFREAD_Q["volpiano"]
            ),
            num_ms_full_text_is_proofread=Count(
                "id", filter=PROOFREADING_CHANTS_ARE_PROOFREAD_Q["ms_full_text"]
            ),
            num_ms_full_text_std_is_proofread=Count(
                "id", filter=PROOFREADING_CHANTS_ARE_PROOFREAD_Q["ms_full_text_std"]
            ),
            num_other_fields_is_proofread=Count(
                "id", filter=PROOFREADING_CHANTS_ARE_PROOFREAD_Q["other_fields"]
            ),
        )

        # Aggregate counts for opportunities and totals
        opportunities_agg = Chant.objects.filter(source=source_obj).aggregate(
            total_chants=Count("id"),
            total_chants_needing_proofread=Count(
                "id", filter=PROOFREADING_NEEDS_PROOFREAD_Q
            ),
            volpiano_opportunities=Count(
                "id", filter=Q(volpiano__isnull=False, volpiano__gt="")
            ),
            ms_full_text_opportunities=Count(
                "id",
                filter=Q(
                    manuscript_full_text__isnull=False, manuscript_full_text__gt=""
                ),
            ),
            ms_full_text_std_opportunities=Count(
                "id",
                filter=Q(
                    manuscript_full_text_std_spelling__isnull=False,
                    manuscript_full_text_std_spelling__gt="",
                ),
            ),
        )

        total_individual_fields_to_proofread = (
            to_proofread_agg["num_volpiano_to_proofread"]
            + to_proofread_agg["num_ms_full_text_to_proofread"]
            + to_proofread_agg["num_ms_full_text_std_to_proofread"]
            + to_proofread_agg["num_other_fields_to_proofread"]
        )

        total_individual_fields_actually_proofread = (
            are_proofread_agg["num_volpiano_is_proofread"]
            + are_proofread_agg["num_ms_full_text_is_proofread"]
            + are_proofread_agg["num_ms_full_text_std_is_proofread"]
            + are_proofread_agg["num_other_fields_is_proofread"]
        )

        total_proofread_opportunities = (
            opportunities_agg["volpiano_opportunities"]
            + opportunities_agg["ms_full_text_opportunities"]
            + opportunities_agg["ms_full_text_std_opportunities"]
            + opportunities_agg["total_chants"]  # for other_fields
        )

        if total_proofread_opportunities == 0:
            percent_complete = 100.0
        else:
            percent_complete = round(
                (total_individual_fields_actually_proofread * 100.0)
                / total_proofread_opportunities,
                2,
            )

        stats_obj, created = self.update_or_create(
            source=source_obj,
            defaults={
                "num_volpiano_to_proofread": to_proofread_agg[
                    "num_volpiano_to_proofread"
                ],
                "num_ms_full_text_to_proofread": to_proofread_agg[
                    "num_ms_full_text_to_proofread"
                ],
                "num_ms_full_text_std_to_proofread": to_proofread_agg[
                    "num_ms_full_text_std_to_proofread"
                ],
                "num_other_fields_to_proofread": to_proofread_agg[
                    "num_other_fields_to_proofread"
                ],
                "total_chants_in_source": opportunities_agg["total_chants"],
                "total_chants_needing_proofread": opportunities_agg[
                    "total_chants_needing_proofread"
                ],
                "total_proofread_opportunities": total_proofread_opportunities,
                "total_individual_fields_to_proofread": total_individual_fields_to_proofread,
                "percent_complete": percent_complete,
            },
        )
        return stats_obj, created


class ProofreadingStats(models.Model):

    source = models.OneToOneField(
        Source, on_delete=models.CASCADE, related_name="proofreading_stats"
    )

    num_volpiano_to_proofread = models.PositiveIntegerField(default=0)
    num_ms_full_text_to_proofread = models.PositiveIntegerField(default=0)
    num_ms_full_text_std_to_proofread = models.PositiveIntegerField(default=0)
    num_other_fields_to_proofread = models.PositiveIntegerField(default=0)

    total_chants_in_source = models.PositiveIntegerField(default=0)
    total_chants_needing_proofread = models.PositiveIntegerField(
        default=0
    )  # Chant-level

    total_proofread_opportunities = models.PositiveIntegerField(
        default=0
    )  # Total checkboxes
    total_individual_fields_to_proofread = models.PositiveIntegerField(
        default=0
    )  # Total unchecked checkboxes

    percent_complete = models.FloatField(default=0.0)  # Will be recalculated

    updated_at = models.DateTimeField(auto_now=True)

    objects = ProofreadingStatsManager()  # Assign the custom manager

    class Meta:
        verbose_name_plural = "Proofreading Stats"

    def __str__(self):
        return f"Stats for {self.source}"
