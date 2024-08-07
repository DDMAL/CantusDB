from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.forms import AdminServiceForm
from main_app.models import Service


@admin.register(Service)
class ServiceAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminServiceForm
