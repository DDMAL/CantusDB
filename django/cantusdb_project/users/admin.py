from django.contrib import admin
from .models import *
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserCreationForm, UserChangeForm

# Register your models here.

class CustomUserCreationForm(UserCreationForm):

    class Meta:
        model = User
        fields = (
            'email', 'password', 'is_active', 'date_joined', 'last_login', 
            'full_name', 'first_name', 'last_name', 'institution', 'city', 
            'country', 'website', 'is_staff', 'groups', 'sources_user_can_edit',
        )


class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = User
        fields = (
            'email', 'password', 'is_active', 'date_joined', 'last_login', 
            'full_name', 'first_name', 'last_name', 'institution', 'city', 
            'country', 'website', 'is_staff', 'groups', 'sources_user_can_edit',
        )


class UserAdmin(BaseUserAdmin):
    form = CustomUserChangeForm
    add_form = CustomUserCreationForm 
    list_display = ('email', 'first_name', 'last_name', 'institution',)
    list_filter = ('groups',)
    fieldsets = (
        ('Account info', {'fields': (('email', 'password'), 'is_active', ('date_joined', 'last_login'))}),
        ('Personal info', {'fields': ('full_name', ('first_name', 'last_name'), 'institution', ('city', 'country'), 'website',)}),
        ('Permissions', {'fields': ('is_staff', 'groups', 'sources_user_can_edit',)}),
    )
    add_fieldsets = (
        ('Account info', {'fields': ('email', ('password1', 'password2'),)}),
        ('Personal info', {'fields': ('full_name', ('first_name', 'last_name'), 'institution', ('city', 'country'), 'website',)}),
        ('Permissions', {'fields': ('is_staff', 'groups', 'sources_user_can_edit',)}),
    )
    search_fields = ('email', 'first_name', 'last_name', 'institution',)
    ordering = ('email',)
    filter_horizontal = ('groups', 'sources_user_can_edit',)

admin.site.register(User, UserAdmin)
