from django.db import models
from main_app.models import BaseModel


class Indexer(BaseModel):
    first_name = models.CharField(max_length=50)
    family_name = models.CharField(max_length=50)
    institution = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=255, blank=True, null=True)
    country = models.CharField(max_length=255, blank=True, null=True)
