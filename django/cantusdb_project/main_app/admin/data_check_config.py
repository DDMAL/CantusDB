from django.contrib import admin

from main_app.models.data_check_config import DataCheckConfig


@admin.register(DataCheckConfig)
class DataCheckConfigAdmin(admin.ModelAdmin):
    list_display = ("frequency", "scope", "last_run")
    list_filter = ("frequency", "scope")
    readonly_fields = ("last_run",)
    filter_horizontal = ("recipients",)

    def has_add_permission(self, request) -> bool:
        # Singleton config: allow creating it once, then only editing that row.
        return not DataCheckConfig.objects.exists()
