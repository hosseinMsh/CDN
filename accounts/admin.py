from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Namespace', {'fields': ('name_spase',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (None, {'fields': ('name_spase',)}),
    )
    list_display = ('username', 'email', 'name_spase', 'is_staff')
    search_fields = ('username', 'email', 'name_spase')