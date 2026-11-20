from django.contrib import admin

from main_app.models import Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "rism_code", "authorities")
    search_fields = ("name", "aliases", "rism_code__iexact", "authorities")

    def has_delete_permission(self, request, obj=None):
        # A saved institution revision can reference even a currently unused country.
        return False
