from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin, EXCLUDE, READ_ONLY
from main_app.forms import AdminSourceForm
from main_app.models import Source


@admin.register(Source)
class SourceAdmin(BaseModelAdmin):
    exclude = EXCLUDE + ("source_status",)

    # These search fields are also available on the user-source inline relationship in the user admin page
    search_fields = (
        "siglum",
        "title",
        "id",
    )
    readonly_fields = READ_ONLY + (
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
