from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.models import Differentia


@admin.register(Differentia)
class DifferentiaAdmin(BaseModelAdmin):
    search_fields = (
        "differentia_id",
        "id",
    )
