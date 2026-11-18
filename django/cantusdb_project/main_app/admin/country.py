from django import forms
from django.contrib import admin
from django.http import HttpRequest

from main_app.models import Country


class CountryAdminForm(forms.ModelForm):
    def clean(self):
        # The admin wraps the entire POST in a transaction. Lock a permanent
        # row before model validation so concurrent edits cannot claim one alias.
        Country.objects.select_for_update().get(pk=Country.NOT_RECORDED)
        return super().clean()


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    form = CountryAdminForm
    list_display = ("name", "getty_id")
    search_fields = ("name", "aliases", "getty_id")

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
