from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.forms import AdminOfficeForm
from main_app.models import Office


@admin.register(Office)
class OfficeAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminOfficeForm
