from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.forms import AdminRismSiglumForm
from main_app.models import RismSiglum


@admin.register(RismSiglum)
class RismSiglumAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminRismSiglumForm
