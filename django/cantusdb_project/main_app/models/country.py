from __future__ import annotations

import re
from collections.abc import Iterable

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, TextField, Value
from django.db.models.functions import Concat, Lower

from main_app.identifiers import COUNTRY_AUTHORITIES


def clean_authorities(records: object) -> dict[str, str]:
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
        pattern, _ = COUNTRY_AUTHORITIES.get(
            label, (r"[A-Za-z0-9][A-Za-z0-9._:-]*", None)
        )
        if not re.fullmatch(pattern, code):
            raise ValidationError(
                f"Invalid {label} record ID {value!r}. Enter the identifier only."
            )
        authorities[label] = code
    return authorities


class CountryQuerySet(models.QuerySet):
    def find_by_name(
        self, name: str, *, reject_ambiguous: bool = False
    ) -> Country | None:
        # The list has a few dozen entries. Use the same Unicode folding as admin validation.
        label = name.strip().casefold()
        if not label:
            return None
        matches = [
            country
            for country in self.only("name", "aliases", "rism_code")
            if label in country.all_names()
        ]
        if len(matches) == 1:
            return matches[0]
        if matches and reject_ambiguous:
            raise ValidationError(
                f"Ambiguous country: {name!r}. Correct the conflicting entries in the admin."
            )
        return None

    def matching(self, query: str, *, prefix: bool = False) -> CountryQuerySet:
        query = query.strip()
        code = Q(rism_code__iexact=query)
        if prefix:
            return self.alias(
                alias_lines=Concat(Value("\n"), "aliases", output_field=TextField())
            ).filter(
                Q(name__istartswith=query)
                | Q(alias_lines__icontains=f"\n{query}")
                | code
            )
        return self.filter(
            Q(name__icontains=query) | Q(aliases__icontains=query) | code
        )


class Country(models.Model):
    objects = CountryQuerySet.as_manager()

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

    def __str__(self) -> str:
        return self.name

    def all_names(self) -> set[str]:
        """Return the case-folded name, aliases, and RISM code for matching."""
        return {
            value.casefold()
            for value in (self.name, *self.aliases.splitlines(), self.rism_code or "")
            if value
        }

    def clean(self) -> None:
        super().clean()
        self.validate_country(Country.objects.exclude(pk=self.pk))

    def normalize_fields(self) -> None:
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
            self.authorities = clean_authorities(self.authorities)
        except ValidationError as exc:
            raise ValidationError({"authorities": exc.messages}) from exc

    def save(self, *args, **kwargs) -> None:
        self.normalize_fields()
        super().save(*args, **kwargs)

    def authority_ids(self) -> set[tuple[str, str]]:
        return {(label.casefold(), code) for label, code in self.authorities.items()}

    def validate_country(self, other_countries: Iterable[Country]) -> None:
        self.normalize_fields()
        names = self.all_names()
        if names.intersection(("[no country]", "not recorded")):
            raise ValidationError(
                "For an unrecorded country, leave the institution’s country blank."
            )
        ids = self.authority_ids()
        for other in other_countries:
            if other.pk == self.pk:
                continue
            if overlap := names & other.all_names():
                raise ValidationError(
                    f"{min(overlap)!r} is already a name, alias, or RISM code for {other.name}."
                )
            if ids & other.authority_ids():
                raise ValidationError(
                    {
                        "authorities": f"An authority record ID already belongs to {other.name}."
                    }
                )
