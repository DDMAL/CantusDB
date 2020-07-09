from django.db import models

from main_app.models import BaseModel


class Century(BaseModel):
    name = models.CharField(max_length=255)
