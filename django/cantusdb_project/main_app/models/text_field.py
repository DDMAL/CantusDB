from typing import Any

from django import forms
from django.db import models
from django.db.backends.base.base import BaseDatabaseWrapper


class NormalizedTextField(models.TextField):
    """Store missing text as an empty string, including direct ORM writes.

    ``trim=False`` preserves indentation and line endings in populated notes
    and rich text. Whitespace-only input is still treated as missing data.
    SQL expressions and raw SQL bypass Python normalization; the database's
    NOT NULL constraint still prevents them from introducing NULL values.
    """

    def __init__(self, *args: Any, trim: bool = True, **kwargs: Any) -> None:
        self.trim = trim
        super().__init__(*args, **kwargs)

    def to_python(self, value: Any) -> str:
        value = super().to_python(value)
        if value is None or not value.strip():
            return ""
        return value.strip() if self.trim else value

    def pre_save(self, model_instance: models.Model, add: bool) -> str:
        # Keep the instance used by post_save receivers consistent with storage,
        # even when full_clean skips None because blank=True.
        value = self.to_python(super().pre_save(model_instance, add))
        setattr(model_instance, self.attname, value)
        return value

    def get_prep_value(self, value: Any) -> str | None:
        # Lookups must keep the caller's spaces (e.g. contains=" et ").
        # TextField.get_prep_value would otherwise call our normalizing to_python.
        return models.TextField.to_python(
            self, models.Field.get_prep_value(self, value)
        )

    def get_db_prep_save(self, value: Any, connection: BaseDatabaseWrapper) -> Any:
        if not hasattr(value, "as_sql"):
            value = self.to_python(value)
        return super().get_db_prep_save(value, connection)

    def formfield(self, **kwargs: Any) -> forms.Field | None:
        kwargs.setdefault("strip", self.trim)
        return super().formfield(**kwargs)

    def deconstruct(self) -> tuple:
        name, path, args, kwargs = super().deconstruct()
        if not self.trim:
            kwargs["trim"] = False
        return name, path, args, kwargs
