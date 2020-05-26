from django.db import models
from main_app.models import BaseModel


class Segment(BaseModel):
    name = models.CharField(max_length=50)
