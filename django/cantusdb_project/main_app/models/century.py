from django.db import models

from main_app.century_dates import century_name_to_dates
from main_app.models import BaseModel


class Century(BaseModel):
    name = models.CharField(max_length=255)
    min_date = models.IntegerField(
        null=True,
        blank=True,
        help_text="Start year of century (e.g., 1400 for 15th century). "
        "When left blank, auto-filled from the name on save if it matches "
        "a known pattern.",
    )
    max_date = models.IntegerField(
        null=True,
        blank=True,
        help_text="End year of century (e.g., 1499 for 15th century). "
        "When left blank, auto-filled from the name on save if it matches "
        "a known pattern.",
    )

    class Meta:
        verbose_name_plural = "centuries"

    def save(self, *args, **kwargs):
        if (self.min_date is None or self.max_date is None) and self.name:
            dates = century_name_to_dates(self.name)
            if dates:
                if self.min_date is None:
                    self.min_date = dates[0]
                if self.max_date is None:
                    self.max_date = dates[1]
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name
