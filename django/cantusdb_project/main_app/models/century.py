from django.db import models

from main_app.models import BaseModel


class Century(BaseModel):
    name = models.CharField(max_length=255)

    class Meta:
        verbose_name_plural = "centuries"

    def __str__(self):
        return self.name
