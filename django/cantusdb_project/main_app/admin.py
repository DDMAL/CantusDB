from django.contrib import admin
from main_app.models import *
from django.contrib.auth import get_user_model
# Register your models here.

class BaseModelAdmin(admin.ModelAdmin):
    exclude = ('created_by', 'last_updated_by')

    def save_model(self, request, obj, form, change):
        if change:
            obj.last_updated_by = request.user
        else:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

class ChantAdmin(BaseModelAdmin):
    pass

class FeastAdmin(BaseModelAdmin):
    pass

class GenreAdmin(BaseModelAdmin):
    pass

class IndexerAdmin(BaseModelAdmin):
    pass

class NotationAdmin(BaseModelAdmin):
    pass

class OfficeAdmin(BaseModelAdmin):
    pass

class ProvenanceAdmin(BaseModelAdmin):
    pass

class SegmentAdmin(BaseModelAdmin):
    pass

class SequenceAdmin(BaseModelAdmin):
    pass

class SourceAdmin(BaseModelAdmin):
    filter_horizontal = ('century', 'notation', 'current_editors', 'inventoried_by', 'full_text_entered_by', 'melodies_entered_by', 'proofreaders', 'other_editors')

admin.site.register(Chant, ChantAdmin)
admin.site.register(Feast, FeastAdmin)
admin.site.register(Genre, GenreAdmin)
admin.site.register(Indexer, IndexerAdmin)
admin.site.register(Notation, NotationAdmin)
admin.site.register(Office, OfficeAdmin)
admin.site.register(Provenance, ProvenanceAdmin)
admin.site.register(Segment, SegmentAdmin)
admin.site.register(Sequence, SequenceAdmin)
admin.site.register(Source, SourceAdmin)
