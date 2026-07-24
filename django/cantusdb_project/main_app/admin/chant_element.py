from django.contrib import admin

from main_app.models import ChantElement


class ChantElementInline(admin.TabularInline):
    """Edit a troped chant's elements alongside the chant itself."""

    model = ChantElement
    extra = 0
    fields = ("order", "kind", "text", "cantus_id", "proposed")
    ordering = ("order",)
