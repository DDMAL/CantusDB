from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from main_app.models import Source

# Register your models here.

# this will allow us to assign sources to users in the User admin page
class SourceInline(admin.TabularInline):
    model = Source.current_editors.through

class UserAdmin(BaseUserAdmin):
    readonly_fields = ('date_joined', 'last_login',)
    list_display = ('email', 'first_name', 'last_name', 'institution',)
    list_filter = ('groups',)
    fieldsets = (
        ('Account info', {'fields': (('email', 'password'), 'is_active', ('date_joined', 'last_login'))}),
        ('Personal info', {'fields': ('full_name', ('first_name', 'last_name'), 'institution', ('city', 'country'), 'website',)}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups',)}),
    )
    add_fieldsets = (
        ('Account info', {'fields': ('email', ('password1', 'password2'),)}),
        ('Personal info', {'fields': ('full_name', ('first_name', 'last_name'), 'institution', ('city', 'country'), 'website',)}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups',)}),
    )
    search_fields = ('email', 'first_name', 'last_name', 'institution',)
    ordering = ('email',)
    filter_horizontal = ('groups',)
    inlines = [SourceInline]

admin.site.register(User, UserAdmin)
