from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.models import Project


@admin.register(Project)
class ProjectAdmin(BaseModelAdmin):
    search_fields = ("name",)
