from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet, TextField, Value
from django.db.models.functions import Concat

from main_app.models import Country


def find_country(name: str, *, reject_ambiguous: bool = False) -> Country | None:
    # The list has a few dozen entries. Use the same Unicode folding as admin validation.
    label = name.strip().casefold()
    if label == "[unknown country]":
        label = "unknown"
    if not label:
        return None
    matches = [
        country
        for country in Country.objects.only("name", "aliases", "rism_code")
        if label in country.lookup_names()
    ]
    if len(matches) == 1:
        return matches[0]
    if matches and reject_ambiguous:
        raise ValidationError(
            f"Ambiguous country: {name!r}. Correct the conflicting entries in the admin."
        )
    return None


def import_rism_country(code: str) -> Country | None:
    if not code.strip():
        return None
    try:
        return Country.objects.get(rism_code__iexact=code.strip())
    except Country.DoesNotExist:
        raise ValidationError(
            f"Unrecognized RISM country code: {code!r}. Check the Country admin."
        ) from None


def import_country(name: str | None) -> Country | None:
    label = (name or "").strip()
    if label.casefold() in ("", "[no country]", "not recorded"):
        return None
    country = find_country(label, reject_ambiguous=True)
    if country is not None:
        return country
    if label.casefold() in ("[unknown country]", "unknown"):
        # Legacy rebuilds distinguish an explicit unknown from the blank used for prints.
        country, _ = Country.objects.get_or_create(
            name__iexact="Unknown", defaults={"name": "Unknown"}
        )
        return country
    raise ValidationError(
        f"Unrecognized country: {name!r}. Add the country or its alias in the admin."
    )


def matching_countries(query: str, *, prefix: bool = False) -> QuerySet[Country]:
    query = query.strip()
    code = Q(rism_code__iexact=query)
    if prefix:
        return Country.objects.alias(
            alias_lines=Concat(Value("\n"), "aliases", output_field=TextField())
        ).filter(
            Q(name__istartswith=query) | Q(alias_lines__icontains=f"\n{query}") | code
        )
    return Country.objects.filter(
        Q(name__icontains=query) | Q(aliases__icontains=query) | code
    )
