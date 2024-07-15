from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.forms import AdminFeastForm
from main_app.models import Feast


@admin.register(Feast)
class FeastAdmin(BaseModelAdmin):
    search_fields = (
        "name",
        "feast_code",
    )
    list_display = (
        "name",
        "month",
        "day",
        "feast_code",
    )
    form = AdminFeastForm
