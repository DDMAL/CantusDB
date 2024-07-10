from main_app.models import BaseModel
from django.db import models


class Project(BaseModel):
    """
    Chants can be tagged with the Project if their inventories are collected
    as part of a particular project or initiative. Tagging a chant with a
    project allows for the collection of project-specific chant data during
    the inventory process and enables filtering by project during search.
    """

    name = models.CharField(max_length=63)

    def __str__(self):
        return f"{self.name} ({self.id})"
