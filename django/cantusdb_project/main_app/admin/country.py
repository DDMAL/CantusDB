from django.contrib import admin
from django.utils.html import format_html, format_html_join

from main_app.identifiers import COUNTRY_AUTHORITIES
from main_app.models import Country


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ("name", "rism_code", "authority_links")
    search_fields = ("name", "aliases", "rism_code__iexact", "authorities")

    @admin.display(description="Authorities")
    def authority_links(self, obj):
        links = []
        for label, code in obj.authorities.items():
            if label in COUNTRY_AUTHORITIES:
                _, template = COUNTRY_AUTHORITIES[label]
                links.append(
                    format_html(
                        '<a href="{}">{} {}</a>', template.format(code), label, code
                    )
                )
            else:
                links.append(f"{label} {code}")
        return format_html_join(", ", "{}", ((link,) for link in links))

    def has_delete_permission(self, request, obj=None):
        # A saved institution revision can reference even a currently unused country.
        return False
