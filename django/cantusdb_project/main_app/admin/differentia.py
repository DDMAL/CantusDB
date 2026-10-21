from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html_join

from main_app.admin.base_admin import BaseModelAdmin, READ_ONLY
from main_app.models import Differentia


@admin.register(Differentia)
class DifferentiaAdmin(BaseModelAdmin):
    search_fields = (
        "differentia_id",
        "id",
    )
    readonly_fields = READ_ONLY + ("related_chants",)

    @admin.display(description="Used by")
    def related_chants(self, obj):
        # Some differentiae have tens of thousands of chants, so link to the
        # filtered admin lists instead of listing them here (#1776).
        if obj.pk is None:
            return "-"
        links = []
        for model, related in (
            ("chant", obj.chant_set),
            ("sequence", obj.sequence_set),
        ):
            count = related.count()
            if count:
                url = reverse(f"admin:main_app_{model}_changelist")
                links.append((url, obj.pk, count, model if count == 1 else f"{model}s"))
        if not links:
            return "No chants or sequences"
        return format_html_join(
            ", ", '<a href="{}?diff_db__id__exact={}">{} {}</a>', links
        )
