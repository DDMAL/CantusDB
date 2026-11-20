from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from main_app.data.countries_v1 import COUNTRIES
from main_app.data.country_wikidata_v1 import WIKIDATA_BY_COUNTRY
from main_app.models import Country


class Command(BaseCommand):
    help = "Add the curated Cantus countries with their stable IDs, aliases and authority IDs."

    @transaction.atomic
    def handle(self, *args, **options):
        # Serialize concurrent imports on a row present in every migrated database.
        Country.objects.select_for_update().get(pk=Country.NOT_RECORDED)
        existing = {country.pk: country for country in Country.objects.all()}
        owners = {
            label: country
            for country in existing.values()
            for label in country.lookup_names()
        }
        added = []
        for pk, name, getty_id, *aliases in COUNTRIES:
            if pk in existing:
                continue  # Preserve edits, including removed aliases and authority IDs.
            country = Country(
                pk=pk,
                name=name,
                aliases="\n".join(aliases),
                authorities={
                    "getty_tgn": getty_id,
                    "wikidata": WIKIDATA_BY_COUNTRY[pk],
                },
            )
            for label in country.lookup_names():
                if label in owners:
                    raise CommandError(
                        f"{name} conflicts with an existing name or alias for {owners[label]}."
                    )
            added.append(country)
        Country.objects.bulk_create(added)
        self.stdout.write(f"Added {len(added)} countries.")
