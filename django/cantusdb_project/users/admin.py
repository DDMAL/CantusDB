from django.contrib import admin
from .models import User, Group, GroupMembership
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import Group as BaseGroup
from main_app.models import Source
from main_app.forms import AdminUserChangeForm

# Register your models here.


# this will allow us to assign sources to users in the User admin page
class SourceInline(admin.TabularInline):
    model = Source.current_editors.through
    raw_id_fields = ["source"]
    ordering = ("source__holding_institution__siglum",)
    verbose_name_plural = "Sources assigned to User"


class GroupMembershipInline(admin.TabularInline):
    """
    Inline admin for seeing which users are in a particular group.
    """

    model = GroupMembership
    can_delete = True
    extra = 1
    verbose_name_plural = "Permissions"
    template = "group_membership_inline.html"


class UserAdmin(BaseUserAdmin):
    readonly_fields = (
        "date_joined",
        "last_login",
    )
    # fields that are displayed on the user list page of the admin
    list_display = (
        "email",
        "full_name",
        "first_name",
        "last_name",
        "institution",
    )
    # creates a filter on the right side of the page to filter users by group
    list_filter = (
        "groups_new",
        "is_indexer",
        "is_superuser",
        "is_staff",
    )
    fieldsets = (
        (
            "Account info",
            {
                "fields": (
                    ("email", "password"),
                    "is_active",
                    ("date_joined", "last_login"),
                )
            },
        ),
        (
            "Personal info",
            {
                "fields": (
                    "full_name",
                    ("first_name", "last_name"),
                    "institution",
                    ("city", "country"),
                    "website",
                ),
                "description": "You can enter a user's first and last name, but these are "
                "only ever displayed in the Admin area - on the main site, users' "
                "full names are always used rather than their first and last name.",
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_superuser",
                    "is_staff",
                    "is_indexer",
                )
            },
        ),
    )
    add_fieldsets = (
        (
            "Account info",
            {
                "fields": (
                    "email",
                    ("password1", "password2"),
                )
            },
        ),
        (
            "Personal info",
            {
                "fields": (
                    "full_name",
                    ("first_name", "last_name"),
                    "institution",
                    ("city", "country"),
                    "website",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_superuser",
                    "is_staff",
                    "is_indexer",
                )
            },
        ),
    )
    search_fields = (
        "email",
        "full_name",
        "first_name",
        "last_name",
        "institution",
    )
    ordering = ("full_name",)
    inlines = [GroupMembershipInline, SourceInline]
    form = AdminUserChangeForm


class ReadOnlyGroupMembershipInline(GroupMembershipInline):
    readonly_fields = ("user", "group", "expiration")
    can_delete = False


class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "description")
    inlines = [ReadOnlyGroupMembershipInline]


admin.site.register(User, UserAdmin)
# Unregister the admin for django.contrib.auth Group model,
# since we use our own custom Group model.
admin.site.unregister(BaseGroup)
admin.site.register(Group, GroupAdmin)
