import re

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Lower

from main_app.data.countries_v1 import CANADA_ID, matching_ids
from main_app.identifiers import ExternalIdentifiers, TYPE_PREFIX

# Only authority IDs are stored. Link destinations come from these trusted bases.
AUTHORITIES = {
    "getty_tgn": ("Getty TGN", r"[0-9]{1,32}", "https://vocab.getty.edu/tgn/"),
    "wikidata": (
        "Wikidata",
        r"Q[1-9][0-9]*",
        TYPE_PREFIX[ExternalIdentifiers.WIKIDATA][1],
    ),
}


class Country(models.Model):
    NOT_RECORDED = -1
    UNKNOWN = -2
    CANADA = CANADA_ID

    name = models.CharField(max_length=64)
    aliases = models.TextField(
        blank=True, help_text="Enter one alternate name per line."
    )
    authorities = models.JSONField(
        default=dict,
        blank=True,
        help_text='Enter authority IDs, for example {"getty_tgn": "7005685", "wikidata": "Q16"}.',
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "countries"
        constraints = [
            models.UniqueConstraint(Lower("name"), name="unique_country_name_ci"),
            models.UniqueConstraint(
                KeyTextTransform("getty_tgn", "authorities"),
                name="unique_country_getty_tgn",
            ),
            models.UniqueConstraint(
                KeyTextTransform("wikidata", "authorities"),
                name="unique_country_wikidata",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def lookup_names(self) -> set[str]:
        return {
            value.strip().casefold()
            for value in [self.name, *self.aliases.splitlines()]
            if value.strip()
        }

    def catalogue_id(self):
        ids = matching_ids(self.lookup_names(), self.authorities.get("getty_tgn"))
        if len(ids) > 1:
            raise ValidationError(
                "The name, aliases, and identifiers refer to different countries."
            )
        return next(iter(ids), None)

    def validate_authorities(self):
        if self.authorities is None:
            self.authorities = {}
        if not isinstance(self.authorities, dict):
            raise ValidationError({"authorities": "Enter an object of authority IDs."})
        for key, value in self.authorities.items():
            if key not in AUTHORITIES:
                raise ValidationError(
                    {"authorities": f"Unsupported country authority: {key}."}
                )
            label, pattern, _ = AUTHORITIES[key]
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise ValidationError({"authorities": f"Invalid {label} ID."})

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.aliases = "\n".join(
            line.strip() for line in self.aliases.splitlines() if line.strip()
        )
        self.validate_authorities()
        reserved_pk = self.catalogue_id()
        labels = self.lookup_names()
        for other in Country.objects.exclude(pk=self.pk):
            overlap = labels & other.lookup_names()
            if overlap:
                raise ValidationError(
                    f"{min(overlap)!r} is already a name or alias for {other.name}."
                )
            if self.pk is None and other.pk == reserved_pk:
                raise ValidationError(
                    "This catalogue country already exists. Edit its existing record."
                )
        if self.pk is not None and reserved_pk not in (None, self.pk):
            raise ValidationError(
                "These details belong to a different catalogue country."
            )

    def save(self, *args, **kwargs):
        self.validate_authorities()
        # Adding a recognised country in the admin before running the loader
        # must give it the same ID as importing it. Never overwrite a renamed row.
        if self._state.adding and self.pk is None:
            pk = self.catalogue_id()
            if pk is not None:
                self.pk = pk
                kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    @property
    def authority_links(self):
        return [
            (label, base_url + self.authorities[key])
            for key, (label, _, base_url) in AUTHORITIES.items()
            if key in self.authorities
        ]
