from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString

from main_app.models.data_check_report import DataCheckReport


@admin.register(DataCheckReport)
class DataCheckReportAdmin(admin.ModelAdmin):
    list_display = ("created_at", "download_link", "completed")
    list_display_links = ("created_at",)
    list_editable = ("completed",)
    list_filter = ("completed",)
    readonly_fields = ("created_at", "download_link")
    fields = ("created_at", "download_link", "completed", "notes")

    def download_link(self, obj: DataCheckReport) -> SafeString:
        if not obj.file:
            return format_html("—")
        return format_html('<a href="{}">Download</a>', obj.file.url)

    download_link.short_description = "Report"  # type: ignore[attr-defined]

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Reports are only ever created by run_data_checks, never by hand.
        return False
