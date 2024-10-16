from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin, EXCLUDE, READ_ONLY
from main_app.forms import AdminSequenceForm
from main_app.models import Sequence


@admin.register(Sequence)
class SequenceAdmin(BaseModelAdmin):
    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("source__holding_institution", "genre", "service")
        )

    @admin.display(description="Source Siglum")
    def get_source_siglum(self, obj):
        if obj.source:
            return obj.source.short_heading

    search_fields = (
        "title",
        "incipit",
        "cantus_id",
        "id",
    )
    exclude = EXCLUDE + (
        "c_sequence",
        "next_chant",
        "is_last_chant_in_feast",
        "visible_status",
    )
    list_display = ("incipit", "get_source_siglum", "genre")
    list_filter = (
        "genre",
        "service",
    )
    raw_id_fields = (
        "source",
        "feast",
    )
    readonly_fields = READ_ONLY + ("incipit",)
    ordering = ("source__holding_institution__siglum", "source__shelfmark")
    form = AdminSequenceForm
