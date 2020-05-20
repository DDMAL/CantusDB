from django.db import models
from main_app.models import CustomBaseModel


class Sequence(CustomBaseModel):
    title = models.CharField(max_length=100)
    siglum = models.CharField(blank=True, null=True, max_length=100)
    incpit = models.CharField(blank=True, null=True, max_length=255)
    folio = models.CharField(blank=True, null=True, max_length=20)
    sequence = models.CharField(blank=True, null=True, max_length=255)
    genre = models.ForeignKey("Genre", blank=True, null=True, on_delete=models.PROTECT)
    rubric = models.CharField(blank=True, null=True, max_length=255)
    analecta_hymnica = models.CharField(blank=True, null=True, max_length=100)
    indexing_notes = models.TextField(blank=True, null=True)
    date = models.CharField(blank=True, null=True, max_length=50)
    ah_volume = models.CharField(blank=True, null=True, max_length=20)
    source = models.ForeignKey(
        "Source", blank=True, null=True, on_delete=models.PROTECT
    )
    cantus_id = models.CharField(max_length=25)
    image_link = models.URLField(blank=True, null=True)
