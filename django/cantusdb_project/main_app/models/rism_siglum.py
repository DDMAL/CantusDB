from django.db import models
from main_app.models import BaseModel


class RismSiglum(BaseModel):
    """The `RismSiglum` model, a foreign key to the `Source` model
    
    The `name` attribute takes the form of Country code, a dash, an indicator of a city in uppercase, 
    and an indicator of an institution in lower-case. 

    Example: GB-Lbl stands for Great Britain, London, British Library
    """

    name = models.CharField(max_length=255)
    description = models.TextField(null=True, blank=True)
    
    class Meta:
        verbose_name = "RISM siglum"
        verbose_name_plural = "RISM sigla"

    def __str__(self):
        return self.name
    