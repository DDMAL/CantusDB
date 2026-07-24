from typing import Optional

from django.db import models

from main_app.models.base_model import BaseModel


class ChantElement(BaseModel):
    """
    One positioned piece of a troped chant's text.

    A troped chant's full text is an ordered sequence of elements. Core elements are
    chunks of the base chant's own text; component elements are the tropes interleaved
    between them. Position is just `order`.
    """

    class Kind(models.TextChoices):
        CORE = "core", "Core"
        COMPONENT = "component", "Component"

    chant = models.ForeignKey(
        "Chant",
        related_name="elements",
        on_delete=models.CASCADE,
    )
    order = models.PositiveSmallIntegerField()
    kind = models.CharField(max_length=16, choices=Kind.choices)
    text = models.TextField()
    # Blank on core elements: they sit under the parent chant's ID, and storing a copy
    # of it here would make an element-level count of a Cantus ID double-count the base
    # chant once per chunk. Components carry their own ID — a sub-ID of the parent
    # (g02711:01) or a wholly separate one (a shared doxology's 909030).
    cantus_id = models.CharField(
        blank=True, null=True, max_length=255, db_index=True, verbose_name="cantus ID"
    )
    # Set on a component the user is proposing to Cantus Index. Sub-IDs are assigned by
    # CI, not here, so a proposed element has no cantus_id until CI catalogues it.
    proposed = models.BooleanField(default=False)

    class Meta:
        ordering = ["order"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.order}: {self.text[:50]}"

    @property
    def resolved_cantus_id(self) -> Optional[str]:
        """The element's own Cantus ID, falling back to the parent chant's for cores."""
        return self.cantus_id or self.chant.cantus_id
