from typing import Any, Optional

from django import forms
from django.db import models


def _normalize(value: Optional[str]) -> Optional[str]:
    if isinstance(value, str):
        return value.strip().replace(" ", "%20")
    return value


class NormalizedURLFormField(forms.URLField):
    """Form URLField that encodes spaces before Django's URLValidator fires."""

    def to_python(self, value: Any) -> str:
        return super().to_python(_normalize(value))


class NormalizedURLField(models.URLField):
    """
    Model URLField that strips whitespace and percent-encodes spaces.

    Normalizes on validation (full_clean) and on save (get_prep_value), so
    forms, admin, management commands, and direct ORM writes all benefit.
    """

    def to_python(self, value: Any) -> Optional[str]:
        return super().to_python(_normalize(value))

    def get_prep_value(self, value: Any) -> Optional[str]:
        return super().get_prep_value(_normalize(value))

    def formfield(self, **kwargs: Any) -> Optional[forms.Field]:
        kwargs.setdefault("form_class", NormalizedURLFormField)
        return super().formfield(**kwargs)

    def deconstruct(self) -> tuple:
        # Report as plain URLField so makemigrations doesn't see a field change.
        name, _, args, kwargs = super().deconstruct()
        return name, "django.db.models.URLField", args, kwargs
