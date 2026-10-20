
from django.contrib import admin
from .models import AuditLog, EmployeeProfile


@admin.register(EmployeeProfile)
class EmployeeProfileAdmin(admin.ModelAdmin):
    list_display = (
        "employee_id",
        "user",
        "department",
        "job_title",
        "date_joined",
    )
    search_fields = (
        "employee_id",
        "user__username",
        "user__email",
    )
    list_filter = ("department",)



@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "timestamp",
        "actor",
        "action",
        "target_user",
        "ip_address",
    )
    list_filter = ("action", "timestamp")
    search_fields = (
        "actor__username",
        "target_user__username",
        "details",
    )
    readonly_fields = (
        "actor",
        "target_user",
        "action",
        "details",
        "ip_address",
        "timestamp",
    )
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User


# Customize the built-in Django Users list
admin.site.unregister(User)


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = (
        "username",
        "email",
        "first_name",
        "last_name",
        "is_active",
        "is_staff",
        "is_superuser",
    )
