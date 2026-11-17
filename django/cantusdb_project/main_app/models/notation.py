from django.db import models
from main_app.models import BaseModel


class Notation(BaseModel):
    """A notation term of the Clavis Sequentiarum (Bower sources only).

    Named as such so it stays apart from a future Cantus DB list (#2330).
    """

    name = models.CharField(max_length=63)

    class Meta:
        verbose_name = "sequence notation"
        verbose_name_plural = "sequence notations (Clavis Sequentiarum)"

    def __str__(self):
        return f"{self.name} ({self.id})"
