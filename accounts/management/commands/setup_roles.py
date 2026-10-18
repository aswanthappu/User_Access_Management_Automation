
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from accounts.models import EmployeeProfile


class Command(BaseCommand):
    help = "Create the initial application roles"

    def handle(self, *args, **options):
        roles = {
            "Administrator": ["add", "change", "view", "delete"],
            "Manager": ["view"],
            "Employee": [],
        }

        content_type = ContentType.objects.get_for_model(
            EmployeeProfile
        )

        for role_name, actions in roles.items():
            group, created = Group.objects.get_or_create(
                name=role_name
            )

            permissions = Permission.objects.filter(
                content_type=content_type,
                codename__in=[
                    f"{action}_employeeprofile"
                    for action in actions
                ],
            )

            group.permissions.set(permissions)

            self.stdout.write(
                f"{'Created' if created else 'Updated'} role: "
                f"{role_name}"
            )
