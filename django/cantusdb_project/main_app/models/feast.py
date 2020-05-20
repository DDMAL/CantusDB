from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import CheckConstraint, Q

from main_app.models import CustomBaseModel


class Feast(CustomBaseModel):
    name = models.CharField()
    description = models.TextField()
    feast_code = models.CharField(max_length=20)
    notes = models.TextFied(blank=True, null=True)
    # Why is there feast_date and also month and day?
    feast_date = models.CharField(blank=True, null=True, max_length=6)
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
