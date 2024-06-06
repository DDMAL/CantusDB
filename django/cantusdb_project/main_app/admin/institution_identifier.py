from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.models import InstitutionIdentifier


@admin.register(InstitutionIdentifier)
class InstitutionIdentifierAdmin(BaseModelAdmin):
    pass
