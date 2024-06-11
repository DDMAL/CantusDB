from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.forms import AdminGenreForm
from main_app.models import Genre


@admin.register(Genre)
class GenreAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminGenreForm
