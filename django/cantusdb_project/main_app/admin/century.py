from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.forms import AdminCenturyForm
from main_app.models import Century


@admin.register(Century)
class CenturyAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminCenturyForm
