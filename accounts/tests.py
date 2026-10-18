
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.test import RequestFactory
from accounts.signals import get_request_ip

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

    def test_employee_creation_writes_audit_logs(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse("accounts:employee_create"),
            {
                "employee_id": "NEW100",
                "username": "new_employee",
                "first_name": "New",
                "last_name": "Employee",
                "email": "new_employee@example.com",
                "department": "IT",
                "job_title": "IT Support",
                "role": self.employee_group.pk,
                "password": "StrongTestPass123!",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:employee_list"),
        )
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin,
                target_user__username="new_employee",
                action="USER_CREATED",
            ).exists()
        )
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin,
                target_user__username="new_employee",
                action="ROLE_CHANGED",
            ).exists()
        )

    def test_employee_update_writes_audit_log(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "accounts:employee_edit",
                kwargs={"pk": self.target_profile.pk},
            ),
            {
                "employee_id": "TEST100",
                "username": "target_user",
                "first_name": "Updated",
                "last_name": "Employee",
                "email": "target@example.com",
                "department": "IT",
                "job_title": "Senior IT Support",
                "role": self.employee_group.pk,
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:employee_list"),
        )
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin,
                target_user=self.target_user,
                action="USER_UPDATED",
            ).exists()
        )

    def test_role_change_writes_audit_log(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "accounts:employee_edit",
                kwargs={"pk": self.target_profile.pk},
            ),
            {
                "employee_id": "TEST100",
                "username": "target_user",
                "first_name": "Test",
                "last_name": "Employee",
                "email": "target@example.com",
                "department": "IT",
                "job_title": "Test Employee",
                "role": self.manager_group.pk,
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:employee_list"),
        )
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin,
                target_user=self.target_user,
                action="ROLE_CHANGED",
            ).exists()
        )
        self.assertTrue(
            self.target_user.groups.filter(
                name="Manager"
            ).exists()
        )

    def test_deactivation_writes_audit_log(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "accounts:employee_edit",
                kwargs={"pk": self.target_profile.pk},
            ),
            {
                "employee_id": "TEST100",
                "username": "target_user",
                "first_name": "Test",
                "last_name": "Employee",
                "email": "target@example.com",
                "department": "IT",
                "job_title": "Test Employee",
                "role": self.employee_group.pk,
                # is_active omitted to deactivate the account
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:employee_list"),
        )

        self.target_user.refresh_from_db()
        self.assertFalse(self.target_user.is_active)

        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.admin,
                target_user=self.target_user,
                action="USER_DEACTIVATED",
            ).exists()
        )

    def test_password_change_writes_audit_log(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "TestPassword123!",
                "new_password1": "NewStrongPassword456!",
                "new_password2": "NewStrongPassword456!",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:password_change_done"),
        )
        self.assertTrue(
            AuditLog.objects.filter(
                actor=self.employee,
                target_user=self.employee,
                action="PASSWORD_CHANGED",
            ).exists()
        )


    def test_audit_log_cannot_be_added_in_admin(self):
        from accounts.admin import AuditLogAdmin
        from django.contrib.admin.sites import AdminSite

        model_admin = AuditLogAdmin(AuditLog, AdminSite())
        self.assertFalse(model_admin.has_add_permission(None))

    def test_audit_log_cannot_be_changed_in_admin(self):
        from accounts.admin import AuditLogAdmin
        from django.contrib.admin.sites import AdminSite

        model_admin = AuditLogAdmin(AuditLog, AdminSite())
        self.assertFalse(model_admin.has_change_permission(None))

    def test_audit_log_cannot_be_deleted_in_admin(self):
        from accounts.admin import AuditLogAdmin
        from django.contrib.admin.sites import AdminSite

        model_admin = AuditLogAdmin(AuditLog, AdminSite())
        self.assertFalse(model_admin.has_delete_permission(None))

    def test_get_request_ip_returns_none_without_request(self):
        self.assertIsNone(get_request_ip(None))

    def test_get_request_ip_uses_forwarded_for_header(self):
        request = RequestFactory().get(
            "/",
            HTTP_X_FORWARDED_FOR="203.0.113.10, 10.0.0.1",
        )
        self.assertEqual(get_request_ip(request), "203.0.113.10")

    def test_get_request_ip_uses_remote_addr_without_forwarded_header(self):
        request = RequestFactory().get(
            "/",
            REMOTE_ADDR="127.0.0.1",
        )
        self.assertEqual(get_request_ip(request), "127.0.0.1")

    def test_employee_list_filters(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse("accounts:employee_list"),
            {
                "q": self.target_user.username,
                "department": self.target_profile.department,
                "role": "Employee",
                "status": "active",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_role"], "Employee")
        self.assertEqual(response.context["selected_status"], "active")