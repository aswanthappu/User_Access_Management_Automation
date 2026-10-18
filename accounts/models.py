
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
