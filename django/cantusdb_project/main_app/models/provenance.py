from django.db import models
from main_app.models import CustomBaseModel


class Provenance(CustomBaseModel):
    name = models.CharField(max_length=3)
    description = models.TextField()
