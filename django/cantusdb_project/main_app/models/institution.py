from django.db import models

from main_app.models import BaseModel


region_help_text = """Province / State / Canton / County. Used to disambiguate cities, e.g., "London (Ontario)"."""
city_help_text = """City / Town / Village / Settlement"""
private_collector_help = """Mark this institution as private collector."""


class Institution(BaseModel):
    name = models.CharField(max_length=255, default="s.n.")
    siglum = models.CharField(max_length=32, default="XX-Nn")
    is_private_collector = models.BooleanField(
        default=False,
        help_text=private_collector_help,
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
        blank=True, null=True, help_text="Notes about this institution that are not publicly visible."
    )

    def __str__(self) -> str:
        sigl: str = f"({self.siglum})" if self.siglum else ""
        return f"{self.name} {sigl}"
