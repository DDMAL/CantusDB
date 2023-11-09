from main_app.models import BaseModel
from django.db import models


class CantusIdentifier(BaseModel):
    cantus_id = models.CharField(blank=False, null=False, max_length=255)

    # Some Cantus IDs are associated with more than one genre.
    genre = models.ManyToManyField(
        "Genre", related_name="cantus_identifiers", blank=True
    )
    full_text = models.TextField(null=True, blank=True)
    cao_sources = models.CharField(blank=True, null=True, max_length=255)
    cao = models.CharField(blank=True, null=True, max_length=255)
    concordances = models.JSONField(blank=True, null=True)

    def __str__(self):
        return self.cantus_id
