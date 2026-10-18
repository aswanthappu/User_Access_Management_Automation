
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from accounts.models import EmployeeProfile, AuditLog

User = get_user_model()


class AccessControlTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin_group = Group.objects.get_or_create(
            name="Administrator"
        )[0]
        cls.manager_group = Group.objects.get_or_create(
            name="Manager"
        )[0]
        cls.employee_group = Group.objects.get_or_create(
            name="Employee"
        )[0]

        cls.admin = User.objects.create_user(
            username="test_admin",
            password="TestPassword123!",
        )
        cls.admin.groups.add(cls.admin_group)

        cls.manager = User.objects.create_user(
            username="test_manager",
            password="TestPassword123!",
        )
        cls.manager.groups.add(cls.manager_group)

        cls.employee = User.objects.create_user(
            username="test_employee",
            password="TestPassword123!",
        )
        cls.employee.groups.add(cls.employee_group)

        cls.target_user = User.objects.create_user(
            username="target_user",
            password="TestPassword123!",
        )
        cls.target_user.groups.add(cls.employee_group)

        cls.target_profile = EmployeeProfile.objects.create(
            user=cls.target_user,
            employee_id="TEST100",
            department="IT",
            job_title="Test Employee",
        )

    def test_manager_can_view_employees(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("accounts:employee_list")
        )

        self.assertEqual(response.status_code, 200)

    def test_manager_cannot_add_employee(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("accounts:employee_create")
        )

        self.assertRedirects(
            response,
            reverse("accounts:dashboard"),
        )

    def test_manager_cannot_edit_employee(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "accounts:employee_edit",
                kwargs={"pk": self.target_profile.pk},
            )
        )

        self.assertRedirects(
            response,
            reverse("accounts:dashboard"),
        )

    def test_employee_cannot_view_employee_management(self):
        self.client.force_login(self.employee)

        response = self.client.get(
            reverse("accounts:employee_list")
        )

        self.assertRedirects(
            response,
            reverse("accounts:dashboard"),
        )

    def test_employee_cannot_view_audit_logs(self):
        self.client.force_login(self.employee)

        response = self.client.get(
            reverse("accounts:audit_logs")
        )

        self.assertRedirects(
            response,
            reverse("accounts:dashboard"),
        )

    def test_manager_cannot_view_audit_logs(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("accounts:audit_logs")
        )

        self.assertRedirects(
            response,
            reverse("accounts:dashboard"),
        )

    def test_administrator_can_view_audit_logs(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("accounts:audit_logs")
        )

        self.assertEqual(response.status_code, 200)

    def test_inactive_user_cannot_log_in(self):
        inactive_user = User.objects.create_user(
            username="inactive_test",
            password="TestPassword123!",
            is_active=False,
        )

        login_success = self.client.login(
            username="inactive_test",
            password="TestPassword123!",
        )

        self.assertFalse(login_success)
