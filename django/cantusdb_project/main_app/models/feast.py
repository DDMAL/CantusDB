from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, Q

from main_app.models import BaseModel


class Feast(BaseModel):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    feast_code = models.PositiveIntegerField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    month = models.PositiveIntegerField(
        blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    day = models.PositiveIntegerField(
        blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(31)]
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(Q(month__gte=1) & Q(month__lte=12)), name="month_gte_1_lte_12"
            ),
            models.CheckConstraint(
                check=(Q(day__gte=1) & Q(day__lte=31)), name="day_gte_1_lte_31"
            ),
        ]
