from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString
from reversion.admin import VersionAdmin

from main_app.models.data_check_report import DataCheckReport


@admin.register(DataCheckReport)
class DataCheckReportAdmin(VersionAdmin):
    # Not BaseModelAdmin: DataCheckReport has no created_by/date_created
    # fields (unlike BaseModel-derived models), but `completed`/`notes` are
    # human-edited and worth a diffable history, hence VersionAdmin directly.
    list_display = ("created_at", "download_link", "completed")
    list_display_links = ("created_at",)
    list_editable = ("completed",)
    list_filter = ("completed",)
    readonly_fields = ("created_at", "download_link")
    fields = ("created_at", "download_link", "completed", "notes")

    def get_urls(self) -> list:
        urls = [
            path(
                "<int:pk>/download/",
                self.admin_site.admin_view(self.download_view),
                name="main_app_datacheckreport_download",
            ),
        ]
        return urls + super().get_urls()

    def download_view(self, request: HttpRequest, pk: int) -> HttpResponse:
        # admin_view() already confirmed the user is staff and active; this
        # checks the model-level permission, same as the admin list/detail pages.
        if not self.has_view_permission(request):
            raise PermissionDenied
        report = DataCheckReport.objects.filter(pk=pk).first()
        if report is None or not report.file:
            raise Http404
        filename = report.file.name.rsplit("/", 1)[-1]
        return FileResponse(
            report.file.open("rb"), as_attachment=True, filename=filename
        )

    def download_link(self, obj: DataCheckReport) -> SafeString:
        if not obj.file:
            return format_html("—")
        url = reverse("admin:main_app_datacheckreport_download", args=[obj.pk])
        return format_html('<a href="{}">Download</a>', url)

    download_link.short_description = "Report"  # type: ignore[attr-defined]

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Reports are only ever created by run_data_checks, never by hand.
        return False
