from django.db import models

from main_app.cluster_structure import normalize_segments
from main_app.models.base_model import BaseModel


class ClusterSegment(BaseModel):
    """One positioned piece of a troped chant: either base text or a trope.

    Exactly one of three shapes, enforced in the database as well as in ``clean()``:

    - **base-text range** — ``[start, end)``, half-open token indices into the parent
      cluster's frozen ``base_text``. The base chant's own words, referenced not copied.
    - **catalogued trope** — a foreign key to a shared ``TropeElement``.
    - **inline trope text** — free text, for a trope Cantus Index has not catalogued.

    ``order`` alone determines the rendered sequence. Base ranges may therefore appear out
    of base-text order (reordering) or more than once (a repetendum), and tropes sit
    wherever the cataloguer put them. Nothing about a segment's position is expressed in
    base-text coordinates, so there is no "insert before token N" anchor that can go
    stale — which is what makes an omitted range a derived fact rather than a stored one.

    Write through ``ChantCluster.set_structure``, not directly: canonicalising the list
    (merging contiguous neighbours, renumbering ``order``) is a whole-cluster operation
    that no single row's ``clean()`` can perform.
    """

    cluster = models.ForeignKey(
        "ChantCluster", related_name="segments", on_delete=models.CASCADE
    )
    order = models.PositiveSmallIntegerField()
    start = models.PositiveSmallIntegerField(
        blank=True, null=True, help_text="First base-text token, inclusive"
    )
    end = models.PositiveSmallIntegerField(
        blank=True, null=True, help_text="Last base-text token, exclusive"
    )
    element = models.ForeignKey(
        "TropeElement", blank=True, null=True, on_delete=models.PROTECT
    )
    text = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["order"]
        constraints = [
            # Deferred so renumbering `order` across a cluster can't trip the constraint
            # mid-transaction on a swap.
            models.UniqueConstraint(
                fields=["cluster", "order"],
                name="cluster_segment_unique_order",
                deferrable=models.Deferrable.DEFERRED,
            ),
            models.CheckConstraint(
                condition=models.Q(start__isnull=True)
                | models.Q(end__gt=models.F("start")),
                name="cluster_segment_end_after_start",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(start__isnull=False)
                        & models.Q(end__isnull=False)
                        & models.Q(element__isnull=True)
                        & models.Q(text="")
                    )
                    | (
                        models.Q(start__isnull=True)
                        & models.Q(end__isnull=True)
                        & models.Q(element__isnull=False)
                        & models.Q(text="")
                    )
                    | (
                        models.Q(start__isnull=True)
                        & models.Q(end__isnull=True)
                        & models.Q(element__isnull=True)
                        & ~models.Q(text="")
                    )
                ),
                name="cluster_segment_exactly_one_shape",
            ),
        ]

    def __str__(self) -> str:
        if self.start is not None:
            return f"{self.order}: base [{self.start}, {self.end})"
        if self.element_id is not None:
            return f"{self.order}: trope {self.element.cantus_id}"
        return f"{self.order}: {self.text[:50]}"

    @property
    def is_core(self) -> bool:
        """Whether this segment is base text rather than a trope."""
        return self.start is not None

    @property
    def resolved_text(self) -> str:
        """This segment's own words: the base-text span, or the trope's text."""
        if self.start is not None:
            return " ".join(self.cluster.base_tokens[self.start : self.end])
        if self.element_id is not None:
            return self.element.text
        return self.text

    def clean(self) -> None:
        super().clean()
        if self.cluster_id is None:
            return
        # Run this segment through the shared validator so a direct or admin write can't
        # bypass the shape and bounds rules. `element_id` stands in for the instance:
        # normalize_segments only tests the trope reference for presence, and the
        # normalised result is discarded here.
        normalize_segments(
            self.cluster.base_token_count,
            [
                {
                    "start": self.start,
                    "end": self.end,
                    "element": self.element_id,
                    "text": self.text,
                }
            ],
        )
