from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet, TextField, Value
from django.db.models.functions import Concat

from main_app.models import Country


def _countries_with_alias_lines() -> QuerySet[Country]:
    # Delimit the first and last alias too, so lookups can match whole lines.
    return Country.objects.alias(
        alias_lines=Concat(
            Value("\n"), "aliases", Value("\n"), output_field=TextField()
        )
    )


def find_country(name: str) -> Country | None:
    label = name.strip()
    if not label or "\n" in label or "\r" in label:
        return None
    return (
        _countries_with_alias_lines()
        .filter(Q(name__iexact=label) | Q(alias_lines__icontains=f"\n{label}\n"))
        .first()
    )


def import_country(name: str | None) -> Country:
    if not name or not name.strip():
        return Country.objects.get(pk=Country.NOT_RECORDED)
    country = find_country(name)
    if country is None:
        raise ValidationError(
            f"Unrecognized country: {name!r}. Add the country or its alias in the admin."
        )
    return country


def matching_countries(query: str, *, prefix: bool = False) -> QuerySet[Country]:
    query = query.strip()
    if prefix:
        return _countries_with_alias_lines().filter(
            Q(name__istartswith=query) | Q(alias_lines__icontains=f"\n{query}")
        )
    return Country.objects.filter(
        Q(name__icontains=query) | Q(aliases__icontains=query)
    )
