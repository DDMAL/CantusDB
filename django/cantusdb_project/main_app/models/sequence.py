from django.contrib.postgres.fields import JSONField
from django.db import models
from main_app.models import BaseModel


class Sequence(BaseModel):
    visible_status = models.CharField(max_length=1, blank=True, null=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    incipit = models.CharField(blank=True, null=True, max_length=255)
    siglum = models.CharField(blank=True, null=True, max_length=255)
    folio = models.CharField(blank=True, null=True, max_length=255)
    sequence = models.CharField(blank=True, null=True, max_length=255)
    genre = models.ForeignKey("Genre", blank=True, null=True, on_delete=models.PROTECT)
    rubrics = models.CharField(blank=True, null=True, max_length=255)
    analecta_hymnica = models.CharField(blank=True, null=True, max_length=255)
    indexing_notes = models.TextField(blank=True, null=True)
    date = models.CharField(blank=True, null=True, max_length=255)

    col1 = models.CharField(blank=True, null=True, max_length=255)
    col2 = models.CharField(blank=True, null=True, max_length=255)
    col3 = models.CharField(blank=True, null=True, max_length=255)

    ah_volume = models.CharField(blank=True, null=True, max_length=255)
    source = models.ForeignKey(
        "Source", blank=True, null=True, on_delete=models.PROTECT
    )
    cantus_id = models.CharField(blank=True, null=True, max_length=255)
    image_link = models.URLField(blank=True, null=True)
    json_info = JSONField(null=True, blank=True)
