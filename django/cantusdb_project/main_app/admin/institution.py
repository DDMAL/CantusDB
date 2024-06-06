from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.models import Institution


@admin.register(Institution)
class InstitutionAdmin(BaseModelAdmin):
    pass
