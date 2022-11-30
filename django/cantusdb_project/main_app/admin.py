from django.contrib import admin
from main_app.models import *
# Register your models here.

class BaseModelAdmin(admin.ModelAdmin):
    # these fields should not be editable
    exclude = ('created_by', 'last_updated_by')

    # if an object is created in the admin interface, assign the user to the created_by field
    # else if an object is updated in the admin interface, assign the user to the last_updated_by field
    def save_model(self, request, obj, form, change):
        if change:
            obj.last_updated_by = request.user
        else:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

class CenturyAdmin(BaseModelAdmin):
    pass

class ChantAdmin(BaseModelAdmin):
    pass

class FeastAdmin(BaseModelAdmin):
    pass

class GenreAdmin(BaseModelAdmin):
    pass

class NotationAdmin(BaseModelAdmin):
    pass

class OfficeAdmin(BaseModelAdmin):
    pass

class ProvenanceAdmin(BaseModelAdmin):
    pass

class RismSiglumAdmin(BaseModelAdmin):
    pass

class SegmentAdmin(BaseModelAdmin):
    pass

class SequenceAdmin(BaseModelAdmin):
    pass

class SourceAdmin(BaseModelAdmin):
    # from the Django docs:
    # Adding a ManyToManyField to this list will instead use a nifty unobtrusive JavaScript “filter” interface
    # that allows searching within the options. The unselected and selected options appear in two boxes side by side.
    filter_horizontal = ('century', 'notation', 'current_editors', 'inventoried_by', 'full_text_entered_by', 'melodies_entered_by', 'proofreaders', 'other_editors')

admin.site.register(Century, CenturyAdmin)
admin.site.register(Chant, ChantAdmin)
admin.site.register(Feast, FeastAdmin)
admin.site.register(Genre, GenreAdmin)
admin.site.register(Notation, NotationAdmin)
admin.site.register(Office, OfficeAdmin)
admin.site.register(Provenance, ProvenanceAdmin)
admin.site.register(RismSiglum, RismSiglumAdmin)
admin.site.register(Segment, SegmentAdmin)
admin.site.register(Sequence, SequenceAdmin)
admin.site.register(Source, SourceAdmin)
