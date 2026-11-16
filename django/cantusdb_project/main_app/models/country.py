from django.db import models


class Country(models.Model):
    """A shared, locally maintained Getty country or an explicit missing value."""

    code = models.CharField(max_length=32, primary_key=True)
    name = models.CharField(max_length=128, unique=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"

    def __str__(self) -> str:
        return self.name

    @property
    def getty_url(self) -> str:
        if self.code.isdecimal():
            return f"https://vocab.getty.edu/tgn/{self.code}"
        return ""
