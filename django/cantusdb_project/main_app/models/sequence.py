from django.db import models
from main_app.models import BaseModel


class Sequence(BaseModel):
    title = models.CharField(max_length=255, blank=True, null=True)
    siglum = models.CharField(blank=True, null=True, max_length=255)
    incipit = models.CharField(blank=True, null=True, max_length=255)
    folio = models.CharField(blank=True, null=True, max_length=255)
    sequence = models.CharField(blank=True, null=True, max_length=255)
    genre = models.ForeignKey("Genre", blank=True, null=True, on_delete=models.PROTECT)
    rubric = models.CharField(blank=True, null=True, max_length=255)
    analecta_hymnica = models.CharField(blank=True, null=True, max_length=255)
    indexing_notes = models.TextField(blank=True, null=True)
    date = models.CharField(blank=True, null=True, max_length=255)
    ah_volume = models.CharField(blank=True, null=True, max_length=255)
    source = models.ForeignKey(
        "Source", blank=True, null=True, on_delete=models.PROTECT
    )
    cantus_id = models.CharField(blank=True, null=True, max_length=255)
    image_link = models.URLField(blank=True, null=True)
