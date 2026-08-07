from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.models import TropeElement


@admin.register(TropeElement)
class TropeElementAdmin(BaseModelAdmin):
    list_display = ("cantus_id", "genre", "incipit")
    list_filter = ("genre",)
    # Backs the autocomplete on ClusterSegmentInline's `element` field.
    search_fields = (
        "cantus_id",
        "text",
    )

    @admin.display(description="incipit")
    def incipit(self, obj: TropeElement) -> str:
        return " ".join(obj.text.split()[:8])
