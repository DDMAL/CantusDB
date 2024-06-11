from django.db import models

from main_app.models import BaseModel


region_help_text = """Province / State / Canton / County. Used to disambiguate cities, e.g., "London (Ontario)"."""
city_help_text = """City / Town / Village / Settlement"""


class Institution(BaseModel):
    name = models.CharField(max_length=255, default="s.n.")
    siglum = models.CharField(max_length=32, default="XX-Nn")
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

    def __str__(self) -> str:
        names: list = [self.name]
        if self.siglum:
            names.append(f"({self.siglum})")
        return " ".join(names)
