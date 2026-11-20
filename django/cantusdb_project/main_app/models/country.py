import re

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import models
from django.db.models.fields.json import KeyTextTransform
from django.db.models.functions import Lower
from django.urls import reverse

from main_app.data.countries_v1 import CANADA_ID
from main_app.data.country_wikidata_v1 import catalogue_ids
from main_app.identifiers import ExternalIdentifiers, TYPE_PREFIX

# These two catalogues also accept the compact IDs used by the country loader.
CATALOGUE_SHORTCUTS = {
    "getty_tgn": ("Getty TGN", r"[0-9]{1,32}", "https://vocab.getty.edu/tgn/"),
    "wikidata": (
        "Wikidata",
        r"Q[1-9][0-9]*",
        TYPE_PREFIX[ExternalIdentifiers.WIKIDATA][1],
    ),
}
validate_record_url = URLValidator(schemes=["https", "http"])


def parse_authority(label, value):
    if not isinstance(label, str) or not label.strip() or not isinstance(value, str):
        raise ValidationError(
            {"authorities": "Enter a database name and a record URL."}
        )
    label, value = label.strip(), value.strip()
    for key, (title, pattern, prefix) in CATALOGUE_SHORTCUTS.items():
        if label.casefold() in (key, title.casefold()):
            identifier = value.removeprefix(prefix)
            if not re.fullmatch(pattern, identifier):
                raise ValidationError({"authorities": f"Invalid {title} ID."})
            return key, identifier
    try:
        validate_record_url(value)
    except ValidationError:
        raise ValidationError(
            {"authorities": f"Enter a full HTTP or HTTPS record URL for {label}."}
        ) from None
    # A different spelling of the label still identifies the same catalogue record.
    for key, (_, pattern, prefix) in CATALOGUE_SHORTCUTS.items():
        if value.startswith(prefix) and re.fullmatch(pattern, value[len(prefix) :]):
            return key, value[len(prefix) :]
    return label, value


class Country(models.Model):
    NOT_RECORDED = -1
    UNKNOWN = -2
    CANADA = CANADA_ID

    name = models.CharField(max_length=64)
    aliases = models.TextField(
        blank=True, help_text="Enter one alternate name per line."
    )
    catalogue_loaded = models.BooleanField(default=False, editable=False)
    authorities = models.JSONField(
        default=dict,
        blank=True,
        help_text="Enter database names and full record URLs. Getty TGN and Wikidata also accept short IDs. "
        'Example for Canada: {"GeoNames": "https://www.geonames.org/6251999/", "wikidata": "Q16"}.',
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

    @property
    def detail_url(self):
        if self.pk not in (self.UNKNOWN, self.NOT_RECORDED):
            return reverse("country-detail", args=[self.pk])
        return None

    def lookup_names(self) -> set[str]:
        return {
            value.strip().casefold()
            for value in [self.name, *self.aliases.splitlines()]
            if value.strip()
        }

    def catalogue_id(self):
        ids = catalogue_ids(self.lookup_names(), self.authorities)
        if len(ids) > 1:
            raise ValidationError(
                "The name, aliases, and identifiers refer to different countries."
            )
        pk = next(iter(ids), None)
        if self.pk is not None and pk not in (None, self.pk):
            raise ValidationError(
                "These details belong to a different catalogue country."
            )
        return pk

    def validate_authorities(self):
        if self.authorities is None:
            self.authorities = {}
        if not isinstance(self.authorities, dict):
            raise ValidationError(
                {"authorities": "Enter a JSON object of country authorities."}
            )
        normalized = {}
        labels = set()
        urls = set()
        for label, raw_value in self.authorities.items():
            key, value = parse_authority(label, raw_value)
            if key.casefold() in labels:
                raise ValidationError({"authorities": f"{label} is listed twice."})
            if value in urls:
                raise ValidationError(
                    {"authorities": f"The record URL for {label} is listed twice."}
                )
            if key not in CATALOGUE_SHORTCUTS:
                urls.add(value)
            labels.add(key.casefold())
            normalized[key] = value
        self.authorities = normalized
        return urls

    def clean(self):
        super().clean()
        self.name = self.name.strip()
        self.aliases = "\n".join(
            line.strip() for line in self.aliases.splitlines() if line.strip()
        )
        custom_urls = self.validate_authorities()
        existing_pks = set()
        labels = self.lookup_names()
        for other in Country.objects.exclude(pk=self.pk):
            if custom_urls.intersection(other.authorities.values()):
                raise ValidationError(
                    {"authorities": f"A record URL already belongs to {other.name}."}
                )
            overlap = labels & other.lookup_names()
            if overlap:
                raise ValidationError(
                    f"{min(overlap)!r} is already a name or alias for {other.name}."
                )
            existing_pks.add(other.pk)
        reserved_pk = self.catalogue_id()
        if self.pk is None and reserved_pk in existing_pks:
            raise ValidationError(
                "This catalogue country already exists. Edit its existing record."
            )

    def save(
        self, force_insert=False, force_update=False, using=None, update_fields=None
    ):
        self.validate_authorities()
        # Adding a recognised country in the admin before running the loader
        # must give it the same ID as importing it. Never overwrite a renamed row.
        catalogue_pk = self.catalogue_id()
        if self._state.adding:
            if self.pk is None:
                self.pk = catalogue_pk
            if self.pk is not None and self.pk < 0:
                # A failed insert leaves the assigned key on this instance.
                # A retry must still insert, even if its fields have changed.
                force_insert = True
        elif not force_insert and update_fields is None:
            # Only the loader writes its receipt. An edit opened before it ran
            # must not mark the country as eligible to load again.
            deferred = self.get_deferred_fields()
            update_fields = [
                field.name
                for field in self._meta.concrete_fields
                if field.editable
                and not field.primary_key
                and field.attname not in deferred
            ]
        return super().save(
            force_insert=force_insert,
            force_update=force_update,
            using=using,
            update_fields=update_fields,
        )

    @property
    def authority_links(self):
        links = []
        for key, (label, pattern, prefix) in CATALOGUE_SHORTCUTS.items():
            value = self.authorities.get(key)
            if isinstance(value, str) and re.fullmatch(pattern, value):
                links.append((label, prefix + value))
        for label in sorted(
            self.authorities.keys() - CATALOGUE_SHORTCUTS.keys(), key=str.casefold
        ):
            url = self.authorities[label]
            try:
                validate_record_url(url)
            except ValidationError:
                continue
            links.append((label, url))
        return links
