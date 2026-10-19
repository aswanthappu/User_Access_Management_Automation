
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.test import RequestFactory
from accounts.signals import get_request_ip
from django.test import RequestFactory
from accounts.views import get_client_ip
from unittest.mock import patch
from django.contrib.messages import get_messages
from django.urls import reverse
from django.http import HttpResponse
from accounts.views import role_required

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
        

    def test_employee_list_inactive_filter(self):
        self.client.force_login(self.manager)

        self.target_user.is_active = False
        self.target_user.save(update_fields=["is_active"])

        response = self.client.get(
            reverse("accounts:employee_list"),
            {"status": "inactive"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_status"], "inactive")
        self.assertIn(
            self.target_profile,
            response.context["employees"],
        )

    
    def test_audit_logs_pagination(self):
        self.client.force_login(self.admin)

        AuditLog.objects.all().delete()

        AuditLog.objects.bulk_create([
            AuditLog(
                actor=self.admin,
                target_user=self.target_user,
                action="LOGIN",
                details=f"Pagination test {i}",
            )
            for i in range(25)
        ])

        response = self.client.get(
            reverse("accounts:audit_logs"),
            {"page": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertEqual(response.context["page_obj"].paginator.count, 25)
        self.assertEqual(len(response.context["page_obj"].object_list), 5)

    def test_get_client_ip_uses_forwarded_header(self):
        request = RequestFactory().get(
            "/",
            HTTP_X_FORWARDED_FOR="203.0.113.10, 192.168.1.5",
        )

        self.assertEqual(
            get_client_ip(request),
            "203.0.113.10",
        )

    def test_audit_logs_invalid_action_filter(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("accounts:audit_logs"),
            {"action": "INVALID_ACTION"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_action"], "")

    def test_password_change_invalid_form(self):
        self.client.force_login(self.employee)

        response = self.client.post(
            reverse("accounts:password_change"),
            {
                "old_password": "WrongOldPassword123!",
                "new_password1": "DifferentPassword123!",
                "new_password2": "DifferentPassword123!",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "accounts/password_change.html"
        )
        self.assertFalse(
            AuditLog.objects.filter(
                actor=self.employee,
                action="PASSWORD_CHANGED",
            ).exists()
        )
    def test_employee_creation_failure_shows_error(self):
        self.client.force_login(self.admin)

        with patch(
            "accounts.views.write_audit_log",
            side_effect=Exception("Test failure"),
        ):
            response = self.client.post(
                reverse("accounts:employee_create"),
                {
                    "employee_id": "NEW101",
                    "username": "new_employee2",
                    "first_name": "New",
                    "last_name": "Employee",
                    "email": "new_employee2@example.com",
                    "department": "IT",
                    "job_title": "IT Support",
                    "role": self.employee_group.pk,
                    "password": "StrongTestPass123!",
                },
            )

        self.assertEqual(response.status_code, 200)
        messages_list = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any(
                "Employee creation failed" in str(message)
                for message in messages_list
            )
        )
    def test_employee_update_failure_shows_error(self):
        self.client.force_login(self.admin)

        with patch(
            "accounts.views.write_audit_log",
            side_effect=Exception("Test update failure"),
        ):
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

        self.assertEqual(response.status_code, 200)

        messages_list = list(get_messages(response.wsgi_request))
        self.assertTrue(
            any(
                "Update failed" in str(message)
                for message in messages_list
            )
        )
    def test_employee_edit_get_prefills_current_data(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse(
                "accounts:employee_edit",
                kwargs={"pk": self.target_profile.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "accounts/employee_edit.html",
        )
        self.assertIn("form", response.context)
        self.assertIn("employee", response.context)
        self.assertEqual(
            response.context["form"].initial["username"],
            self.target_user.username,
        )
        self.assertEqual(
            response.context["form"].initial["role"],
            self.employee_group.pk,
        )
    def test_password_change_succeeds_if_audit_logging_fails(self):
        self.client.force_login(self.employee)

        with patch(
            "accounts.views.write_audit_log",
            side_effect=Exception("Audit logging failure"),
        ):
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

        self.employee.refresh_from_db()
        self.assertTrue(
            self.employee.check_password("NewStrongPassword456!")
        )
    def test_unauthenticated_user_is_redirected_to_login(self):
        response = self.client.get(
            reverse("accounts:employee_list")
        )

        self.assertRedirects(
            response,
            reverse("accounts:login")
            + "?next="
            + reverse("accounts:employee_list"),
        )
    def test_my_profile_displays_employee_profile(self):
        self.client.force_login(self.target_user)

        response = self.client.get(
            reverse("accounts:my_profile")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "accounts/my_profile.html",
        )
        self.assertEqual(
            response.context["employee"],
            self.target_profile,
        )
        
    def test_audit_logs_search_filter(self):
        self.client.force_login(self.admin)

        AuditLog.objects.create(
            actor=self.admin,
            target_user=self.target_user,
            action="LOGIN",
            details="Unique audit search term",
            ip_address="192.0.2.10",
        )

        response = self.client.get(
            reverse("accounts:audit_logs"),
            {"q": "Unique audit search term"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any(
                log.details == "Unique audit search term"
                for log in response.context["page_obj"].object_list
            )
        )

    def test_audit_logs_valid_action_filter(self):
        self.client.force_login(self.admin)

        AuditLog.objects.create(
            actor=self.admin,
            target_user=self.target_user,
            action="LOGIN",
            details="Login filter test",
        )

        response = self.client.get(
            reverse("accounts:audit_logs"),
            {"action": "LOGIN"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["selected_action"],
            "LOGIN",
        )
        self.assertTrue(
            all(
                log.action == "LOGIN"
                for log in response.context["page_obj"].object_list
            )
        )
    def test_employee_create_get_displays_blank_form(self):
        self.client.force_login(self.admin)

        response = self.client.get(
            reverse("accounts:employee_create")
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "accounts/employee_form.html",
        )
        self.assertIn("form", response.context)
        self.assertFalse(response.context["form"].is_bound)
    def test_role_required_redirects_unauthenticated_user(self):
        response = self.client.get(
            reverse("accounts:employee_create")
        )

        self.assertRedirects(
            response,
            reverse("accounts:login")
            + "?next="
            + reverse("accounts:employee_create"),
        )
    def test_role_required_redirects_unauthenticated_user(self):
        from django.contrib.auth.models import AnonymousUser
        from django.http import HttpResponse
        from accounts.views import role_required

        @role_required()
        def dummy_view(request):
            return HttpResponse("Allowed")

        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        response = dummy_view(request)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse("accounts:login"),
        )