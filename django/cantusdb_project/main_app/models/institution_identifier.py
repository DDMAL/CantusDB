from django.db import models

from main_app.identifiers import IDENTIFIER_TYPES
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
