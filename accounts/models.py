
from django.conf import settings
from django.db import models


class EmployeeProfile(models.Model):
    DEPARTMENT_CHOICES = [
        ("IT", "Information Technology"),
        ("HR", "Human Resources"),
        ("FINANCE", "Finance"),
        ("SECURITY", "Security"),
        ("OPERATIONS", "Operations"),
        ("OTHER", "Other"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="employee_profile",
    )
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(
        max_length=20,
        choices=DEPARTMENT_CHOICES,
        default="OTHER",
    )
    job_title = models.CharField(max_length=100, blank=True)
    date_joined = models.DateField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.employee_id} - {self.user.username}"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ("USER_CREATED", "User Created"),
        ("USER_UPDATED", "User Updated"),
        ("USER_ACTIVATED", "User Activated"),
        ("USER_DEACTIVATED", "User Deactivated"),
        ("ROLE_CHANGED", "Role Changed"),
        ("PASSWORD_CHANGED", "Password Changed"),
        ("LOGIN", "Login"),
        ("LOGOUT", "Logout"),
    ]

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_actions",
    )
    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"

    def __str__(self):
        return f"{self.get_action_display()} - {self.timestamp}"
