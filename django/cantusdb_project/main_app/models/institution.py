from django.db import models
from django.db.models import CheckConstraint, Q

from main_app.models import BaseModel


region_help_text = """Province / State / Canton / County. Used to disambiguate cities, e.g., "London (Ontario)"."""
city_help_text = """City / Town / Village / Settlement"""
private_collector_help = """Mark this institution as private collector."""
private_collection_help = """Mark this instititution as being a private collection. This is used to identify private 
collectors regardless of whether they have a RISM siglum or not.
"""


class Institution(BaseModel):
    class Meta:
        ordering = ["country", "city", "name"]
        constraints = [
            CheckConstraint(
                check=~(Q(is_private_collector=True) & Q(siglum__isnull=False)),
                name="siglum_and_private_not_valid",
                violation_error_message="Siglum and Private Collector cannot both be specified.",
            ),
            CheckConstraint(
                check=(Q(is_private_collector=True) | Q(siglum__isnull=False)),
                name="at_least_one_of_siglum_or_private_collector",
                violation_error_message="At least one of Siglum or Private Collector must be specified.",
            ),
        ]

    name = models.CharField(max_length=255, default="s.n.")
    siglum = models.CharField(
        verbose_name="RISM Siglum",
        max_length=32,
        blank=True,
        null=True,
        help_text="Reserved for assigned RISM sigla",
    )
    is_private_collector = models.BooleanField(
        default=False,
        help_text=private_collector_help,
    )
    is_private_collection = models.BooleanField(
        default=False,
        help_text=private_collection_help,
    )
    city = models.CharField(
        max_length=64, blank=True, null=True, help_text=city_help_text
    )
    region = models.CharField(
        max_length=64, blank=True, null=True, help_text=region_help_text
    )
    country = models.CharField(max_length=64, default="s.l.")
    alternate_names = models.TextField(
        blank=True, null=True, help_text="Enter alternate names on separate lines."
    )
    former_sigla = models.TextField(
        blank=True, null=True, help_text="Enter former sigla on separate lines."
    )
    private_notes = models.TextField(
        blank=True,
        null=True,
        help_text="Notes about this institution that are not publicly visible.",
    )
    migrated_identifier = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="Former Cantus identifier. Should not be used for new records."
    )

    def __str__(self) -> str:
        sigl: str = f" ({self.siglum})" if self.siglum else ""
        city: str = f"{self.city}, " if self.city else ""
        return f"{city}{self.name}{sigl}"
