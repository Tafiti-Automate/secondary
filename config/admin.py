from django.contrib import admin

from .models import SchoolModule


@admin.register(SchoolModule)
class SchoolModuleAdmin(admin.ModelAdmin):
    list_display = ("school", "code", "is_enabled", "enabled_by", "updated_at")
    list_filter = ("is_enabled", "code")
    search_fields = ("school__name", "code")
