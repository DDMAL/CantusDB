from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html

from main_app.models import Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "getty_record")
    search_fields = ("name", "code")
    readonly_fields = ("name", "code", "getty_record")

    @admin.display(description="Getty TGN")
    def getty_record(self, obj: Country) -> str:
        if obj.getty_url:
            return format_html('<a href="{}">{}</a>', obj.getty_url, obj.code)
        return "—"

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: Country | None = None
    ) -> bool:
        return False

    def has_delete_permission(
        self, request: HttpRequest, obj: Country | None = None
    ) -> bool:
        return False
