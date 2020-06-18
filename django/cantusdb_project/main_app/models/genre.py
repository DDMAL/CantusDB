from django.contrib.postgres.fields import ArrayField
from django.db import models

from main_app.models import BaseModel


class Genre(BaseModel):
    mass_office_choices = [
        ("Mass", "Mass"),
        ("Office", "Office"),
        ("Old Hispanic", "Old Hispanic"),
    ]
    name = models.CharField(max_length=255)
    description = models.TextField()
    mass_office = ArrayField(
        base_field=models.CharField(max_length=12, choices=mass_office_choices), size=3,
    )
