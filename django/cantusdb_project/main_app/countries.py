"""Local Getty TGN country catalogue; see data/README.md for provenance."""

import json
from pathlib import Path

from django.core.exceptions import ValidationError

COUNTRIES = json.loads(
    (Path(__file__).parent / "data" / "countries_20261115.json").read_text()
)
COUNTRY_NAMES = {row["code"]: row["name"] for row in COUNTRIES}
COUNTRY_CODES = {
    name.strip().casefold(): country["code"]
    for country in COUNTRIES
    for name in [country["name"], *country["aliases"]]
}


def country_code(name: str | None) -> str:
    """Resolve an import's country name; reject unrecognized values."""
    try:
        return COUNTRY_CODES[(name or "").strip().casefold()]
    except KeyError:
        raise ValidationError(f"Unrecognized country: {name!r}.") from None


def matching_country_codes(
    query: str, *, prefix: bool = False, prefer_exact: bool = False
) -> list[str]:
    """Include legacy names in searches and existing country filter URLs."""
    query = query.strip().casefold()
    # The country filter selects one country. General text searches must still
    # match substrings: "ca" matches both Canada and the Vatican City alias.
    if prefer_exact and query in COUNTRY_CODES:
        return [COUNTRY_CODES[query]]
    return list(
        {
            code
            for name, code in COUNTRY_CODES.items()
            if (name.startswith(query) if prefix else query in name)
        }
    )
