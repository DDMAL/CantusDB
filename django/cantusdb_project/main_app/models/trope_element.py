from django.db import models

from main_app.models.base_model import BaseModel


class TropeElement(BaseModel):
    """A trope element catalogued by Cantus Index, shared by every chant that uses it.

    Stored once and referenced by ``ClusterSegment``, so a trope's text is not copied
    into each chant that carries it and "which sources contain this trope" is a foreign
    key traversal instead of a string search.

    Uncatalogued tropes deliberately have no row here. Cantus Index assigns the IDs, so a
    trope the cataloguer typed in has none yet and lives as inline text on the segment
    instead; once CI catalogues it, create a TropeElement and repoint the segments at it.
    That keeps ``cantus_id`` genuinely unique rather than nullable-and-unique, which in
    Postgres would permit unlimited ID-less rows and defeat the deduplication.
    """

    cantus_id = models.CharField(max_length=255, unique=True, verbose_name="cantus ID")
    genre = models.ForeignKey("Genre", blank=True, null=True, on_delete=models.PROTECT)
    text = models.TextField()

    class Meta:
        ordering = ["cantus_id"]

    def __str__(self) -> str:
        return f"{self.cantus_id}: {self.text[:50]}"
