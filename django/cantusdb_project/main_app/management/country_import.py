"""Resolve RISM country codes in current and legacy imports."""

from django.core.exceptions import ValidationError

from main_app.countries import import_country
from main_app.models import Country


def import_rism_country(code: str) -> Country | None:
    if not code.strip():
        return None
    try:
        return Country.objects.get(rism_code__iexact=code.strip())
    except Country.DoesNotExist:
        raise ValidationError(
            f"Unrecognized RISM country code: {code!r}. Check the Country admin."
        ) from None


def legacy_rism_code(siglum: str, known_codes: set[str]) -> str:
    prefix, separator, _ = siglum.partition("-")
    if not prefix.isascii() or not prefix.isalpha() or not prefix.isupper():
        return ""
    # These two prefixes occur in the old source records.
    code = {"SA": "ZA", "T": "RC"}.get(prefix, prefix)
    if separator or code == "XX" or code in known_codes:
        return code
    return ""


def stored_rism_codes() -> set[str]:
    return {
        code.upper()
        for code in Country.objects.exclude(rism_code=None).values_list(
            "rism_code", flat=True
        )
    }


def import_legacy_rism_country(code: str) -> Country | None:
    if code == "XX":
        return import_country("Unknown")
    return import_rism_country(code)
