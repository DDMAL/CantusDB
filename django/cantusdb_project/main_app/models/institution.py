from django.db import models

from main_app.models import BaseModel


class Institution(BaseModel):
    name = models.CharField(max_length=255, default="s.n.")
    siglum = models.CharField(max_length=32, default="XX-Nn")
    city = models.CharField(max_length=64, blank=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.siglum})"
