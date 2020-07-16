from django.db import models

from main_app.models import BaseModel


class RismSiglum(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
