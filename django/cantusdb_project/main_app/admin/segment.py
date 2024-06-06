from django.contrib import admin

from main_app.admin.base_admin import BaseModelAdmin
from main_app.forms import AdminSegmentForm
from main_app.models import Segment


@admin.register(Segment)
class SegmentAdmin(BaseModelAdmin):
    search_fields = ("name",)
    form = AdminSegmentForm
