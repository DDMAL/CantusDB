from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.forms import AdminNotationForm
from main_app.models import Notation


@admin.register(Notation)
class NotationAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminNotationForm
