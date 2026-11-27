import csv
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from main_app.models import Country


def read_catalogue():
    seen = set()
    with (Path(settings.BASE_DIR) / "countries.csv").open(
        encoding="utf-8", newline=""
    ) as source:
        for row in csv.DictReader(source):
            try:
                pk = int(row["id"])
            except (TypeError, ValueError) as exc:
                raise CommandError(f"Invalid country ID: {row['id']!r}.") from exc
            if pk < 1 or pk in seen:
                raise CommandError(
                    f"Catalogue IDs must be positive and unique. Found {pk}."
                )
            seen.add(pk)
            ids = {"Getty TGN": row["getty_tgn"], "Wikidata": row["wikidata"]}
            yield Country(
                pk=pk,
                name=row["name"].strip(),
                aliases="\n".join(row["aliases"].split("|")),
                rism_code=row["rism_code"].strip() or None,
                authorities={
                    label: code.strip()
                    for label, code in ids.items()
                    if code and code.strip()
                },
            )


def fill_missing(country, entry):
    known = country.normalized_names()
    if not (
        known & entry.normalized_names()
        or country.authority_ids() & entry.authority_ids()
    ):
        raise CommandError(
            f"Catalogue ID {entry.pk} ({entry.name}) is occupied by {country.name}. "
            "Check the ID and country identity before retrying."
        )
    country.rism_code = country.rism_code or entry.rism_code
    # normalize_fields() keeps the first spelling of each alias after the merge.
    country.aliases = "\n".join((country.aliases, entry.name, entry.aliases))
    country.authorities = entry.authorities | country.authorities


class Command(BaseCommand):
    help = "Add the curated countries and fill missing RISM codes, aliases, and authority IDs."

    @transaction.atomic
    def handle(self, *args, **options):
        # Serialize the import with inserts, including the first import into an empty table.
        table = Country._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f"LOCK TABLE {connection.ops.quote_name(table)} IN SHARE ROW EXCLUSIVE MODE"
            )
        countries = Country.objects.in_bulk()
        original = {
            pk: (c.rism_code, c.aliases, c.authorities) for pk, c in countries.items()
        }
        added = []
        try:
            for country in countries.values():
                # Upgrade recognized links from the earlier draft, including local rows.
                country.normalize_fields(legacy_urls=True)
            for country in read_catalogue():
                country.normalize_fields()
                if country.pk in countries:
                    fill_missing(countries[country.pk], country)
                else:
                    countries[country.pk] = country
                    added.append(country)
            for country in countries.values():
                country.clean_fields()
                country.validate_country(countries.values())
        except ValidationError as exc:
            raise CommandError(
                f"Country {country.pk} ({country.name}): {' '.join(exc.messages)}"
            ) from exc
        updated = [
            country
            for pk, country in countries.items()
            if pk in original
            and original[pk]
            != (country.rism_code, country.aliases, country.authorities)
        ]
        Country.objects.bulk_create(added)
        Country.objects.bulk_update(updated, ["rism_code", "aliases", "authorities"])
        if countries:
            # Explicit catalogue IDs bypass the PostgreSQL identity sequence. Advance it
            # past occupied IDs without recycling higher IDs issued to local countries.
            highest = max(countries)
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT setval(seq::regclass, %s) FROM pg_get_serial_sequence(%s, 'id') AS seq "
                    "WHERE COALESCE(pg_sequence_last_value(seq::regclass), 0) < %s",
                    [highest, table, highest],
                )
        self.stdout.write(
            f"Added {len(added)} countries. Updated {len(updated)} countries."
        )
