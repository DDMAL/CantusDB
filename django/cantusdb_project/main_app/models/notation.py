from django.db import models
from main_app.models import BaseModel


class Notation(BaseModel):
    name = models.CharField(max_length=50)
