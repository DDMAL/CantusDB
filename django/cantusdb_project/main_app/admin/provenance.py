from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.forms import AdminProvenanceForm
from main_app.models import Provenance


@admin.register(Provenance)
class ProvenanceAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminProvenanceForm
