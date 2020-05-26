from django.db import models
from main_app.models import BaseModel


class Office(BaseModel):
    name = models.CharField(max_length=3)
    description = models.TextField()
