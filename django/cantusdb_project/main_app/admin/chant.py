from django.contrib import admin

from main_app.admin.base_admin import EXCLUDE, READ_ONLY, BaseModelAdmin
from main_app.admin.filters import InputFilter
from main_app.forms import AdminChantForm
from main_app.models import Chant


class SourceKeyFilter(InputFilter):
    parameter_name = "source_id"
    title = "Source ID"

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(source_id=self.value())


@admin.register(Chant)
class ChantAdmin(BaseModelAdmin):

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("source__holding_institution", "genre", "office")
        )

    @admin.display(description="Source Siglum")
    def get_source_siglum(self, obj):
        if obj.source:
            return obj.source.short_heading

    list_display = (
        "incipit",
        "get_source_siglum",
        "genre",
    )
    search_fields = (
        "title",
        "incipit",
        "cantus_id",
        "id",
        "source__holding_institution__siglum"
    )

    readonly_fields = READ_ONLY + ("incipit",)

    list_filter = (
        SourceKeyFilter,
        "genre",
        "office",
    )
    exclude = EXCLUDE + (
        "col1",
        "col2",
        "col3",
        "next_chant",
        "s_sequence",
        "is_last_chant_in_feast",
        "visible_status",
        "date",
        "volpiano_notes",
        "volpiano_intervals",
        "title",
        "differentiae_database",
    )
    form = AdminChantForm
    raw_id_fields = (
        "source",
        "feast",
    )
    ordering = ("source__holding_institution__siglum", "source__shelfmark")
