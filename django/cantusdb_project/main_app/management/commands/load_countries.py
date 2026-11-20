import csv
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from main_app.models import Country


class Command(BaseCommand):
    help = "Add the curated countries and fill missing RISM codes, aliases, and authority URLs."

    @transaction.atomic
    def handle(self, *args, **options):
        countries = {
            c.pk: c for c in Country.objects.select_for_update().order_by("pk")
        }
        added, updated = [], []
        seen = set()
        with (Path(settings.BASE_DIR) / "countries.csv").open(
            encoding="utf-8", newline=""
        ) as source:
            for row in csv.DictReader(source):
                try:
                    pk = int(row["id"])
                except ValueError as exc:
                    raise CommandError(f"Invalid country ID: {row['id']!r}.") from exc
                if not 1 <= pk <= 36 or pk in seen:
                    raise CommandError(
                        f"Catalogue IDs must be distinct and between 1 and 36. Found {pk}."
                    )
                seen.add(pk)
                country = countries.get(pk)
                if country is None:
                    country = Country(pk=pk, name=row["name"])
                    countries[pk] = country
                    added.append(country)
                before = (country.rism_code, country.aliases, country.authorities)
                country.rism_code = country.rism_code or row["rism_code"]
                known = country.lookup_names()
                aliases = country.aliases.splitlines()
                for name in [row["name"], *row["aliases"].split("|")]:
                    if name and name.casefold() not in known:
                        aliases.append(name)
                        known.add(name.casefold())
                country.aliases = "\n".join(aliases)
                authorities = dict(country.authorities)
                labels = {label.casefold() for label in authorities}
                for label, url in (
                    ("Getty TGN", row["getty_tgn"]),
                    ("Wikidata", row["wikidata"]),
                ):
                    if (
                        label.casefold() not in labels
                        and url not in authorities.values()
                    ):
                        authorities[label] = url
                country.authorities = authorities
                try:
                    country.clean_fields()
                    country.validate_country(countries.values())
                except ValidationError as exc:
                    raise CommandError(
                        f"Country {pk} ({row['name']}): {' '.join(exc.messages)}"
                    ) from exc
                if not country._state.adding and before != (
                    country.rism_code,
                    country.aliases,
                    country.authorities,
                ):
                    updated.append(country)
        Country.objects.bulk_create(added)
        Country.objects.bulk_update(updated, ["rism_code", "aliases", "authorities"])
        self.stdout.write(
            f"Added {len(added)} countries. Updated {len(updated)} countries."
        )
