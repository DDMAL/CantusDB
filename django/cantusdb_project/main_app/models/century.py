from django.db import models

from main_app.models import BaseModel


class Century(BaseModel):
    name = models.CharField(max_length=255)
    min_date = models.IntegerField(
        null=True,
        blank=True,
        help_text="Start year of century (e.g., 1400 for 15th century)",
    )
    max_date = models.IntegerField(
        null=True,
        blank=True,
        help_text="End year of century (e.g., 1499 for 15th century)",
    )

    class Meta:
        verbose_name_plural = "centuries"

    def __str__(self):
        return self.name
