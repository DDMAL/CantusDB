from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from main_app.models import SiteBanner


@admin.register(SiteBanner)
class SiteBannerAdmin(admin.ModelAdmin):
    fields = ("is_active", "message", "expires_at", "updated_by", "updated_at")
    readonly_fields = ("updated_by", "updated_at")

    def has_add_permission(self, request) -> bool:
        # Singleton: row is created lazily by SiteBanner.load().
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def changelist_view(self, request, extra_context=None):
        # Skip the changelist and jump straight to the singleton's edit form.
        SiteBanner.load()
        return HttpResponseRedirect(
            reverse("admin:main_app_sitebanner_change", args=[1])
        )

    def save_model(self, request, obj, form, change) -> None:
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)
