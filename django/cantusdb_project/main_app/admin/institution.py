from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.models import Institution, InstitutionIdentifier


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

    def get_city_region(self, obj):
        name = [obj.city]
        if obj.region:
            name.append(f"({obj.region})")
        return " ".join(name)

    get_city_region.short_description = "City"
