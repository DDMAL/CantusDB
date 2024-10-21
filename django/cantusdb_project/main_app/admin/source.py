from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin, EXCLUDE, READ_ONLY
from main_app.admin.filters import InputFilter
from main_app.forms import AdminSourceForm
from main_app.models import Source, SourceIdentifier


class SourceKeyFilter(InputFilter):
    parameter_name = "holding_institution__siglum"
    title = "Institution Siglum"

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(holding_institution__siglum__icontains=self.value())


class IdentifiersInline(admin.TabularInline):
    model = SourceIdentifier
    extra = 0

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("source__holding_institution")


@admin.register(Source)
class SourceAdmin(BaseModelAdmin):
    exclude = EXCLUDE + ("source_status",)
    raw_id_fields = ("holding_institution",)
    inlines = (IdentifiersInline,)

    # These search fields are also available on the user-source inline relationship in the user admin page
    search_fields = (
        "shelfmark",
        "holding_institution__siglum",
        "holding_institution__name",
        "holding_institution__migrated_identifier",
        "id",
        "provenance_notes",
        "name",
        "identifiers__identifier"
    )
    readonly_fields = (
        ("title", "siglum")
        + READ_ONLY
        + (
            "number_of_chants",
            "number_of_melodies",
            "date_created",
            "date_updated",
        )
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
        "shelfmark",
        "holding_institution",
        "id",
    )

    list_filter = (
        SourceKeyFilter,
        "full_source",
        "segment",
        "source_status",
        "published",
        "century",
        "holding_institution__is_private_collector",
    )

    ordering = ("holding_institution__siglum", "shelfmark")

    form = AdminSourceForm

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        return queryset.select_related("holding_institution")
