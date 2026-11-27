import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from main_app.identifiers import COUNTRY_AUTHORITIES


def clean_authorities(records, *, legacy_urls=False) -> dict[str, str]:
    if records is None:
        return {}
    if not isinstance(records, dict):
        raise ValidationError("Enter a JSON object of authority names and record IDs.")
    known_labels = {label.casefold(): label for label in COUNTRY_AUTHORITIES}
    authorities = {}
    labels = set()
    for label, value in records.items():
        if not isinstance(label, str) or not label.strip():
            raise ValidationError("Enter an authority name for each record ID.")
        label = label.strip()
        key = label.casefold()
        if key in labels:
            raise ValidationError(f"Duplicate authority name: {label}.")
        labels.add(key)
        label = known_labels.get(key, label)
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ValidationError(f"Enter a record ID for {label}.")
        code = str(value).strip()
        pattern, template = COUNTRY_AUTHORITIES.get(
            label, (r"[A-Za-z0-9][A-Za-z0-9._:-]*", None)
        )
        if legacy_urls and template and code.startswith(("http://", "https://")):
            url = "https://" + code.partition("://")[2].removesuffix("/")
            candidate = url.rsplit("/", 1)[-1]
            if url == template.format(candidate).rstrip("/") or (
                label == "Wikidata"
                and url == f"https://www.wikidata.org/entity/{candidate}"
            ):
                code = candidate
        if not re.fullmatch(pattern, code):
            raise ValidationError(
                f"Invalid {label} record ID {value!r}. Enter the identifier only."
            )
        authorities[label] = code
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
        help_text='Enter authority names and record IDs, for example {"Wikidata": "Q16"}.',
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="unique_country_name_ci")
        ]

    def __str__(self):
        return self.name

    def normalized_names(self) -> set[str]:
        return {
            value.casefold()
            for value in (self.name, *self.aliases.splitlines(), self.rism_code or "")
            if value
        }

    def clean(self):
        super().clean()
        self.validate_country(Country.objects.exclude(pk=self.pk))

    def normalize_fields(self, *, legacy_urls=False):
        self.name = (self.name or "").strip()
        if not self.name:
            raise ValidationError({"name": "Enter a country name."})
        self.rism_code = (self.rism_code or "").strip().upper() or None
        seen = {self.name.casefold(), (self.rism_code or "").casefold(), ""}
        aliases = []
        for line in self.aliases.splitlines():
            alias = line.strip()
            key = alias.casefold()
            if key not in seen:
                aliases.append(alias)
                seen.add(key)
        self.aliases = "\n".join(aliases)
        try:
            self.authorities = clean_authorities(
                self.authorities, legacy_urls=legacy_urls
            )
        except ValidationError as exc:
            raise ValidationError({"authorities": exc.messages}) from exc

    def save(self, *args, **kwargs):
        self.normalize_fields()
        super().save(*args, **kwargs)

    def authority_ids(self) -> set[tuple[str, str]]:
        return {(label.casefold(), code) for label, code in self.authorities.items()}

    def validate_country(self, other_countries):
        self.normalize_fields()
        names = self.normalized_names()
        if names.intersection(("[no country]", "not recorded")):
            raise ValidationError(
                "For an unrecorded country, leave the institution’s country blank."
            )
        ids = self.authority_ids()
        for other in other_countries:
            if other.pk == self.pk:
                continue
            if overlap := names & other.normalized_names():
                raise ValidationError(
                    f"{min(overlap)!r} is already a name, alias, or RISM code for {other.name}."
                )
            if ids & other.authority_ids():
                raise ValidationError(
                    {
                        "authorities": f"An authority record ID already belongs to {other.name}."
                    }
                )
