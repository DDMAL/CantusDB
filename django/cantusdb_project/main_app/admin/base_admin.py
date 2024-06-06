from reversion.admin import VersionAdmin


# these fields should not be editable by all classes
EXCLUDE = ("json_info",)


READ_ONLY = (
    "created_by",
    "last_updated_by",
    "date_created",
    "date_updated",
)


class BaseModelAdmin(VersionAdmin):
    exclude = EXCLUDE
    readonly_fields = READ_ONLY

    # if an object is created in the admin interface, assign the user to the created_by field
    # else if an object is updated in the admin interface, assign the user to the last_updated_by field
    def save_model(self, request, obj, form, change):
        if change:
            obj.last_updated_by = request.user
        else:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
