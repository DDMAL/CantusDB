from collections import defaultdict

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from main_app.data.countries_v1 import COUNTRIES
from main_app.data.country_wikidata_v1 import WIKIDATA_BY_COUNTRY
from main_app.models import Country


class Command(BaseCommand):
    help = "Load the curated countries, aliases and authority IDs once per country."

    @transaction.atomic
    def handle(self, *args, **options):
        # Serialize concurrent imports on a row present in every migrated database.
        Country.objects.select_for_update().get(pk=Country.NOT_RECORDED)
        existing = {
            country.pk: country
            for country in Country.objects.select_for_update().order_by("pk")
        }
        owners = defaultdict(set)
        for country in existing.values():
            for label in country.lookup_names():
                owners[label].add(country.pk)
        added = []
        enriched = []
        for pk, name, getty_id, *aliases in COUNTRIES:
            country = existing.get(pk)
            if country is None:
                country = Country(pk=pk, name=name)
                added.append(country)
            elif country.catalogue_loaded:
                continue
            else:
                enriched.append(country)
            known = country.lookup_names()
            spellings = country.aliases.splitlines()
            for label in (name, *aliases):
                key = label.casefold()
                conflicts = owners[key] - {pk}
                if conflicts:
                    other = existing[min(conflicts)]
                    raise CommandError(
                        f"{name} conflicts with an existing name or alias for {other.name}."
                    )
                if key not in known:
                    spellings.append(label)
                    known.add(key)
            country.aliases = "\n".join(spellings)
            country.authorities = {
                "getty_tgn": getty_id,
                "wikidata": WIKIDATA_BY_COUNTRY[pk],
            } | country.authorities
            country.catalogue_loaded = True
        Country.objects.bulk_create(added)
        Country.objects.bulk_update(
            enriched, ["aliases", "authorities", "catalogue_loaded"]
        )
        self.stdout.write(
            f"Added {len(added)} countries. Enriched {len(enriched)} existing countries."
        )
