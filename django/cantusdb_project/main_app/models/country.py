import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.db.models.functions import Lower


def clean_authorities(records):
    if records is None:
        return {}
    if not isinstance(records, dict):
        raise ValidationError("Enter a JSON object of database names and record URLs.")
    validate_url = URLValidator(schemes=["http", "https"])
    authorities = {}
    labels = set()
    for label, url in records.items():
        if not isinstance(label, str) or not label.strip() or not isinstance(url, str):
            raise ValidationError("Enter a database name and a full record URL.")
        label, url = label.strip(), url.strip()
        validate_url(url)
        item = re.fullmatch(
            r"https?://www\.wikidata\.org/(?:entity|wiki)/(Q[1-9][0-9]*)", url
        )
        if item:
            url = f"https://www.wikidata.org/wiki/{item[1]}"
        if label.casefold() in labels or url in authorities.values():
            raise ValidationError(f"Duplicate database name or record URL for {label}.")
        labels.add(label.casefold())
        authorities[label] = url
    return authorities


class Country(models.Model):
    CANADA = 6

    name = models.CharField(max_length=64)
    aliases = models.TextField(
        blank=True, help_text="Enter one alternate name per line."
    )
    rism_code = models.CharField(
        "RISM country code", max_length=8, unique=True, null=True, blank=True
    )
    authorities = models.JSONField(
        default=dict,
        blank=True,
        help_text="Enter a JSON object of database names and full record URLs.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="unique_country_name_ci")
        ]

    def __str__(self):
        return self.name

    def lookup_names(self):
        return {
            value.casefold()
            for value in (self.name, *self.aliases.splitlines(), self.rism_code or "")
            if value
        }

    def clean(self):
        super().clean()
        self.validate_country(Country.objects.exclude(pk=self.pk))

    def validate_country(self, other_countries):
        self.name = self.name.strip()
        self.aliases = "\n".join(
            line.strip() for line in self.aliases.splitlines() if line.strip()
        )
        self.rism_code = self.rism_code.strip().upper() if self.rism_code else None
        if not self.name:
            raise ValidationError({"name": "Enter a country name."})
        try:
            self.authorities = clean_authorities(self.authorities)
        except ValidationError as exc:
            raise ValidationError({"authorities": exc.messages}) from exc
        names = self.lookup_names()
        if names.intersection(("[no country]", "not recorded")):
            raise ValidationError(
                "For an unrecorded country, leave the institution’s country blank."
            )
        urls = set(self.authorities.values())
        for other in other_countries:
            if other.pk == self.pk:
                continue
            if overlap := names & other.lookup_names():
                raise ValidationError(
                    f"{min(overlap)!r} is already a name, alias, or RISM code for {other.name}."
                )
            if urls.intersection(other.authorities.values()):
                raise ValidationError(
                    {"authorities": f"A record URL already belongs to {other.name}."}
                )
