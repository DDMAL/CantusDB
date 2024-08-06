from django.db import models

from main_app.identifiers import IDENTIFIER_TYPES, TYPE_PREFIX
from main_app.models import BaseModel


class InstitutionIdentifier(BaseModel):
    identifier = models.CharField(
        max_length=512,
        help_text="Do not provide the full URL here; only the identifier.",
    )
    identifier_type = models.IntegerField(choices=IDENTIFIER_TYPES)
    institution = models.ForeignKey(
        "Institution", related_name="identifiers", on_delete=models.CASCADE
    )

    def __str__(self):
        return f"{self.identifier_prefix}:{self.identifier}"

    @property
    def identifier_label(self) -> str:
        d: dict[int, str] = dict(IDENTIFIER_TYPES)
        return d[self.identifier_type]

    @property
    def identifier_prefix(self) -> str:
        (pfx, _) = TYPE_PREFIX[self.identifier_type]
        return pfx

    @property
    def identifier_url(self) -> str:
        (_, url) = TYPE_PREFIX[self.identifier_type]
        return f"{url}{self.identifier}"
