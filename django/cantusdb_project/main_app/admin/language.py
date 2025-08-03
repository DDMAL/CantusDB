from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.models import Language


@admin.register(Language)
class LanguageAdmin(BaseModelAdmin):
    search_fields = ("name",)
