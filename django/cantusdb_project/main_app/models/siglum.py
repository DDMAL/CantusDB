from django.db import models

from main_app.models import BaseModel


class Siglum(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField()
