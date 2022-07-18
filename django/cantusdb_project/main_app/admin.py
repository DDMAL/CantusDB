from django.contrib import admin
from main_app.models import *
from django.contrib.auth import get_user_model
# Register your models here.

class SourcesUserCanEditInline(admin.TabularInline):
    model = get_user_model().sources_user_can_edit.through

class SourceAdmin(admin.ModelAdmin):
    inlines = [SourcesUserCanEditInline]
    filter_horizontal = ('century', 'notation', 'current_editors', 'inventoried_by', 'full_text_entered_by', 'melodies_entered_by', 'proofreaders', 'other_editors')

admin.site.register(Chant)
admin.site.register(Feast)
admin.site.register(Genre)
admin.site.register(Indexer)
admin.site.register(Notation)
admin.site.register(Office)
admin.site.register(Provenance)
admin.site.register(Segment)
admin.site.register(Sequence)
admin.site.register(Source, SourceAdmin)
