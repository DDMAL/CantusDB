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
            urls = {"Getty TGN": row["getty_tgn"], "Wikidata": row["wikidata"]}
            yield Country(
                pk=pk,
                name=row["name"].strip(),
                aliases="\n".join(row["aliases"].split("|")),
                rism_code=row["rism_code"].strip() or None,
                authorities={
                    label: url.strip()
                    for label, url in urls.items()
                    if url and url.strip()
                },
            )


def fill_missing(country, entry):
    known = country.lookup_names()
    if not (
        known & entry.lookup_names()
        or set(country.authorities.values()).intersection(entry.authorities.values())
    ):
        raise CommandError(
            f"Catalogue ID {entry.pk} ({entry.name}) is occupied by {country.name}. "
            "Check the ID and country identity before retrying."
        )
    before = (country.rism_code, country.aliases, country.authorities)
    country.rism_code = country.rism_code or entry.rism_code
    known = country.lookup_names()
    aliases = country.aliases.splitlines()
    for name in (entry.name, *entry.aliases.splitlines()):
        if name and name.casefold() not in known:
            aliases.append(name)
            known.add(name.casefold())
    country.aliases = "\n".join(aliases)
    labels = {label.casefold() for label in country.authorities}
    country.authorities = country.authorities | {
        label: url
        for label, url in entry.authorities.items()
        if label.casefold() not in labels and url not in country.authorities.values()
    }
    return before != (country.rism_code, country.aliases, country.authorities)


class Command(BaseCommand):
    help = "Add the curated countries and fill missing RISM codes, aliases, and authority URLs."

    @transaction.atomic
    def handle(self, *args, **options):
        # Serialize the import with inserts, including the first import into an empty table.
        table = Country._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f"LOCK TABLE {connection.ops.quote_name(table)} IN SHARE ROW EXCLUSIVE MODE"
            )
        countries = Country.objects.in_bulk()
        added, updated = [], []
        for entry in read_catalogue():
            country = countries.get(entry.pk)
            if country is None:
                country = countries[entry.pk] = entry
                added.append(country)
            elif fill_missing(country, entry):
                updated.append(country)
            try:
                country.clean_fields()
                country.validate_country(countries.values())
            except ValidationError as exc:
                raise CommandError(
                    f"Country {entry.pk} ({entry.name}): {' '.join(exc.messages)}"
                ) from exc
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
