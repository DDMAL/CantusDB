from django.db import models

from main_app.models.base_model import BaseModel


class SourceURL(BaseModel):
    """
    A model to store links from sources to external resources.
    """

    class URLTypes(models.IntegerChoices):
        IIIF_MANIFEST = 1, "IIIF Manifest"
        HOST_INSTITUTION_RECORD = 2, "Host Institution Record"
        EXTERNAL_IMAGES = 3, "External Images"

    url = models.URLField(
        max_length=1024,
    )
    source = models.ForeignKey(
        "Source",
        related_name="source_links",
        on_delete=models.CASCADE,
    )
    url_type = models.IntegerField(
        choices=URLTypes.choices,
    )
    url_description = models.CharField(
        max_length=255,
        blank=True,
        null=True,
    )
