from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from main_app.models import Source

# Register your models here.


# this will allow us to assign sources to users in the User admin page
class SourceInline(admin.TabularInline):
    model = Source.current_editors.through


class UserAdmin(BaseUserAdmin):
    readonly_fields = (
        "date_joined",
        "last_login",
    )
    # fields that are displayed on the user list page of the admin
    list_display = (
        "email",
        "first_name",
        "last_name",
        "institution",
    )
    # creates a filter on the right side of the page to filter users by group
    list_filter = ("groups",)
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
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_staff",
                    "is_superuser",
                    "groups",
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
                    "is_staff",
                    "is_superuser",
                    "groups",
                )
            },
        ),
    )
    search_fields = (
        "email",
        "first_name",
        "last_name",
        "institution",
    )
    # order the list of users by email
    ordering = ("email",)
    filter_horizontal = ("groups",)
    inlines = [SourceInline]


admin.site.register(User, UserAdmin)
