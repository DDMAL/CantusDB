from django.db import models

from main_app.models import BaseModel


class Century(BaseModel):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name