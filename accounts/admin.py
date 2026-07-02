from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import AuditLog, User


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("School access", {"fields": ("role", "phone", "profile_picture", "must_change_password", "is_deleted")}),)
    list_display = ("username", "first_name", "last_name", "role", "is_active", "last_activity")
    list_filter = ("role", "is_active", "is_deleted")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "entity_type", "description")
    list_filter = ("action", "entity_type")
    search_fields = ("description", "entity_id", "actor__username")
    readonly_fields = ("created_at",)
