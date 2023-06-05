from django.db import models
from main_app.models import BaseModel


class Provenance(BaseModel):
    name = models.CharField(max_length=63)

    def __str__(self):
        return self.name
