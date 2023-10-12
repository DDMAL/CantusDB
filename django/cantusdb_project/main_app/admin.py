from django.contrib import admin
from main_app.models import *
from main_app.forms import (
    AdminCenturyForm,
    AdminChantForm,
    AdminFeastForm,
    AdminGenreForm,
    AdminNotationForm,
    AdminOfficeForm,
    AdminProvenanceForm,
    AdminRismSiglumForm,
    AdminSegmentForm,
    AdminSequenceForm,
    AdminSourceForm,
)

# these fields should not be editable by all classes
EXCLUDE = (
    "created_by",
    "last_updated_by",
    "json_info",
)


class BaseModelAdmin(admin.ModelAdmin):
    exclude = EXCLUDE

    # if an object is created in the admin interface, assign the user to the created_by field
    # else if an object is updated in the admin interface, assign the user to the last_updated_by field
    def save_model(self, request, obj, form, change):
        if change:
            obj.last_updated_by = request.user
        else:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class CenturyAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminCenturyForm


class ChantAdmin(BaseModelAdmin):
    @admin.display(description="Source Siglum")
    def get_source_siglum(self, obj):
        if obj.source:
            return obj.source.siglum

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
    )

    readonly_fields = (
        "date_created",
        "date_updated",
    )

    list_filter = (
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
    )
    form = AdminChantForm
    raw_id_fields = (
        "source",
        "feast",
    )
    ordering = ("source__siglum",)


class DifferentiaAdmin(BaseModelAdmin):
    search_fields = (
        "differentia_id",
        "id",
    )


class FeastAdmin(BaseModelAdmin):
    search_fields = (
        "name",
        "feast_code",
    )
    list_display = (
        "name",
        "month",
        "day",
        "feast_code",
    )
    form = AdminFeastForm


class GenreAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminGenreForm


class NotationAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminNotationForm


class OfficeAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminOfficeForm


class ProvenanceAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminProvenanceForm


class RismSiglumAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminRismSiglumForm


class SegmentAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminSegmentForm


class SequenceAdmin(BaseModelAdmin):
    @admin.display(description="Source Siglum")
    def get_source_siglum(self, obj):
        if obj.source:
            return obj.source.siglum

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
        "office",
    )
    raw_id_fields = (
        "source",
        "feast",
    )
    ordering = ("source__siglum",)
    form = AdminSequenceForm


class SourceAdmin(BaseModelAdmin):
    # These search fields are also available on the user-source inline relationship in the user admin page
    search_fields = (
        "siglum",
        "title",
        "id",
    )
    readonly_fields = (
        "number_of_chants",
        "number_of_melodies",
        "date_created",
        "date_updated",
    )
    # from the Django docs:
    # Adding a ManyToManyField to this list will instead use a nifty unobtrusive JavaScript “filter” interface
    # that allows searching within the options. The unselected and selected options appear in two boxes side by side.
    filter_horizontal = (
        "century",
        "notation",
        "current_editors",
        "inventoried_by",
        "full_text_entered_by",
        "melodies_entered_by",
        "proofreaders",
        "other_editors",
    )

    list_display = (
        "title",
        "siglum",
        "id",
    )

    list_filter = (
        "full_source",
        "segment",
        "source_status",
        "published",
        "century",
    )

    ordering = ("siglum",)

    form = AdminSourceForm


admin.site.register(Century, CenturyAdmin)
admin.site.register(Chant, ChantAdmin)
admin.site.register(Differentia, DifferentiaAdmin)
admin.site.register(Feast, FeastAdmin)
admin.site.register(Genre, GenreAdmin)
admin.site.register(Notation, NotationAdmin)
admin.site.register(Office, OfficeAdmin)
admin.site.register(Provenance, ProvenanceAdmin)
admin.site.register(RismSiglum, RismSiglumAdmin)
admin.site.register(Segment, SegmentAdmin)
admin.site.register(Sequence, SequenceAdmin)
admin.site.register(Source, SourceAdmin)
