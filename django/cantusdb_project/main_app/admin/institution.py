from django.contrib import admin
from django.urls import reverse
from django.utils.safestring import mark_safe

from main_app.admin.base_admin import BaseModelAdmin
from main_app.models import Institution, InstitutionIdentifier, Source


class InstitutionSourceInline(admin.TabularInline):
    model = Source
    extra = 0
    fields = ("link_id_field", "shelfmark",)
    readonly_fields = ("link_id_field",)

    def link_id_field(self, obj):
        change_url = reverse('admin:main_app_source_change', args=(obj.pk,))
        return mark_safe(f'<a href="{change_url}">{obj.pk}</a>')



class InstitutionIdentifierInline(admin.TabularInline):
    model = InstitutionIdentifier
    extra = 0
    exclude = ["created_by", "last_updated_by"]


@admin.register(Institution)
class InstitutionAdmin(BaseModelAdmin):
    list_display = ("name", "siglum", "get_city_region", "country")
    search_fields = ("name", "siglum", "city", "region", "alternate_names")
    list_filter = ("city",)
    inlines = (InstitutionIdentifierInline,)

    def get_city_region(self, obj) -> str:
        city: str = obj.city if obj.city else "[No city]"
        region: str = f"({obj.region})" if obj.region else ""
        return f"{city} {region}"

    get_city_region.short_description = "City"
