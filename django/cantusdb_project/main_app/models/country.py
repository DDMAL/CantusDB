from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.functions import Lower


class Country(models.Model):
    # Reserved IDs are outside the range allocated to countries by the database.
    NOT_RECORDED = -1
    UNKNOWN = -2

    name = models.CharField(max_length=64)
    aliases = models.TextField(
        blank=True, help_text="Enter one alternate name per line."
    )
    getty_id = models.CharField(
        "Getty TGN ID",
        max_length=32,
        blank=True,
        null=True,
        unique=True,
        validators=[RegexValidator(r"^[0-9]+$", "Enter a numeric Getty TGN ID.")],
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="unique_country_name_ci")
        ]

    def __str__(self) -> str:
        return self.name

    def lookup_names(self) -> set[str]:
        return {
            value.strip().casefold()
            for value in [self.name, *self.aliases.splitlines()]
            if value.strip()
        }

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.aliases = "\n".join(
            line.strip() for line in self.aliases.splitlines() if line.strip()
        )
        labels = self.lookup_names()
        for other in Country.objects.exclude(pk=self.pk):
            overlap = labels & other.lookup_names()
            if overlap:
                raise ValidationError(
                    f"{min(overlap)!r} is already a name or alias for {other.name}."
                )

    @property
    def getty_url(self) -> str:
        return f"https://vocab.getty.edu/tgn/{self.getty_id}" if self.getty_id else ""
