"""Read the country import CSV and index its names and identifiers for admin edits."""

import csv
from functools import cache
from pathlib import Path
from typing import NamedTuple

from django.conf import settings


class CatalogueCountry(NamedTuple):
    pk: int
    name: str
    getty_id: str
    wikidata_id: str
    aliases: tuple[str, ...]


@cache
def catalogue_countries() -> tuple[CatalogueCountry, ...]:
    with (Path(settings.BASE_DIR) / "countries.csv").open(
        encoding="utf-8", newline=""
    ) as source:
        return tuple(
            CatalogueCountry(
                int(row["id"]),
                row["name"],
                row["getty_tgn"],
                row["wikidata"],
                tuple(row["aliases"].split("|")) if row["aliases"] else (),
            )
            for row in csv.DictReader(source)
        )


@cache
def _country_index() -> dict[tuple[str, str], int]:
    index = {}
    for country in catalogue_countries():
        for label in (country.name, *country.aliases):
            index["name", label.casefold()] = country.pk
        index["getty_tgn", country.getty_id] = country.pk
        index["wikidata", country.wikidata_id] = country.pk
    return index


def catalogue_ids(labels, authorities):
    index = _country_index()
    matches = {index["name", label] for label in labels if ("name", label) in index}
    for key in ("getty_tgn", "wikidata"):
        pk = index.get((key, authorities.get(key)))
        if pk is not None:
            matches.add(pk)
    return matches
