from django.db import models
from main_app.models import BaseModel


class Genre(BaseModel):
    name = models.CharField(max_length=15)
    description = models.TextField()
    mass_office = models.CharField(max_length=63, null=True, blank=True)

    def __str__(self):
        return f"[{self.name}] {self.description}"

    @property
    def display_name(self) -> str:
        """Alias for the __str()__ method, useful for templates."""
        return self.__str__()
