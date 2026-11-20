from django.contrib import admin
from django.http import HttpRequest

from main_app.models import Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "authorities")
    search_fields = ("name", "aliases", "authorities")

    def view_on_site(self, obj):
        return obj.detail_url

    def has_change_permission(
        self, request: HttpRequest, obj: Country | None = None
    ) -> bool:
        if obj and obj.pk in (Country.UNKNOWN, Country.NOT_RECORDED):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(
        self, request: HttpRequest, obj: Country | None = None
    ) -> bool:
        # A saved institution revision can reference even a currently unused country.
        return False
