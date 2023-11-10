from main_app.models import BaseModel
from django.db import models


class Differentia(BaseModel):
    differentia_id = models.CharField(
        blank=False, null=False, max_length=255
    )  # values like `129a` get stored here
    melodic_transcription = models.CharField(
        blank=True, null=True, max_length=255
    )  # values like `1--k-k-l-j-k-h--4` get stored here
    mode = models.CharField(blank=True, null=True, max_length=255)
    # differentia database stores information on mode, but we don't expect to ever need to display it
    # saeculorum - DD stores a volpiano snippet about the "saeculorum" part of the differentia, but we don't expect to ever need to display it
    # amen - DD stores a volpiano snippet about the "amen" part of the differentia, but we don't expect to ever need to display it

    class Meta:
        verbose_name_plural = "differentiae"

    def __str__(self) -> str:
        return self.differentia_id
