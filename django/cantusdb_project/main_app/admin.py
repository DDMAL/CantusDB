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

class SourcesUserCanEditInline(admin.TabularInline):
    model = get_user_model().sources_user_can_edit.through

class SourceAdmin(BaseModelAdmin):
    inlines = [SourcesUserCanEditInline]
    filter_horizontal = ('century', 'notation', 'current_editors', 'inventoried_by', 'full_text_entered_by', 'melodies_entered_by', 'proofreaders', 'other_editors')

    def save_model(self, request, obj, form, change):
        # if the current editors for this source has changed,
        # remove this source from the "sources user can edit" set of all users who were previously "current editors",
        # then reassign this source to new "current editors"

        if change:
            obj.last_updated_by = request.user
            old_current_editors = list(self.model.objects.get(id=obj.id).current_editors.all())
            new_current_editors = form.cleaned_data["current_editors"]

            if "current_editors" in form.changed_data:
                for old_editor in old_current_editors:
                    old_editor.sources_user_can_edit.remove(obj)

                for new_editor in new_current_editors:
                    new_editor.sources_user_can_edit.add(obj)

            super().save_model(request, obj, form, change)

        else:
            obj.created_by = request.user
            current_editors = form.cleaned_data["current_editors"]
            super().save_model(request, obj, form, change)

            for editor in current_editors:
                editor.sources_user_can_edit.add(obj)

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
