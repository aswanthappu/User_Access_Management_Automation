
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model, views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordChangeView
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.views.decorators.http import require_POST


from .forms import (
    EmployeeForm,
    EmployeeEditForm,
    ADUserCreateForm,
)
from .models import EmployeeProfile, AuditLog
from django.core.paginator import Paginator

User = get_user_model()


def get_client_ip(request):
    """Get the client's IP address when available."""
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    # Only trust this header when set by a trusted proxy.
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


def write_audit_log(
    request,
    action,
    target_user=None,
    details="",
):
    """Create an audit record for an authenticated user's action."""
    AuditLog.objects.create(
        actor=request.user if request.user.is_authenticated else None,
        target_user=target_user,
        action=action,
        details=details,
        ip_address=get_client_ip(request),
    )


class AppLoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    redirect_authenticated_user = True


class AppLogoutView(auth_views.LogoutView):
    next_page = reverse_lazy("accounts:login")



def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            user = request.user

            if not user.is_authenticated:
                return redirect("accounts:login")

            if (
                user.is_superuser
                or user.groups.filter(name="Administrator").exists()
            ):
                return view_func(request, *args, **kwargs)

            if (
                allowed_roles
                and user.groups.filter(name__in=allowed_roles).exists()
            ):
                return view_func(request, *args, **kwargs)

            messages.error(
                request,
                "You are not authorized to perform this action.",
            )
            return redirect("accounts:dashboard")

        return wrapper

    return decorator



@login_required
def dashboard(request):
    user = request.user

    is_admin = (
        user.is_superuser
        or user.groups.filter(name="Administrator").exists()
    )
    is_manager = user.groups.filter(name="Manager").exists()

    context = {
        "total_users": User.objects.count(),
        "active_users": User.objects.filter(is_active=True).count(),
        "inactive_users": User.objects.filter(is_active=False).count(),
        "total_profiles": EmployeeProfile.objects.count(),
        "can_view_employees": is_admin or is_manager,
        "can_manage_employees": is_admin,
        "can_access_django_admin": user.is_superuser,
    }

    return render(request, "accounts/dashboard.html", context)


@login_required
@role_required("Manager")
def employee_list(request):
    employees = (
        EmployeeProfile.objects
        .select_related("user")
        .prefetch_related("user__groups")
        .order_by("employee_id")
    )

    search_query = request.GET.get("q", "").strip()

    if search_query:
        employees = employees.filter(
            Q(employee_id__icontains=search_query)
            | Q(user__username__icontains=search_query)
            | Q(user__first_name__icontains=search_query)
            | Q(user__last_name__icontains=search_query)
            | Q(user__email__icontains=search_query)
        )

    department = request.GET.get("department", "").strip()
    valid_departments = dict(EmployeeProfile.DEPARTMENT_CHOICES)

    if department in valid_departments:
        employees = employees.filter(department=department)
    else:
        department = ""

    role = request.GET.get("role", "").strip()
    valid_roles = ["Administrator", "Manager", "Employee"]

    if role in valid_roles:
        employees = employees.filter(
            user__groups__name=role
        ).distinct()
    else:
        role = ""

    status = request.GET.get("status", "").strip().lower()

    if status == "active":
        employees = employees.filter(user__is_active=True)
    elif status == "inactive":
        employees = employees.filter(user__is_active=False)
    else:
        status = ""
    print("Logged-in user:", request.user.username)
    print("Authenticated:", request.user.is_authenticated)
    print("Superuser:", request.user.is_superuser)
    print(
           "Administrator group:",
        request.user.groups.filter(name="Administrator").exists(),
    )
    return render(
        
        request,
        "accounts/employee_list.html",
        {
            "employees": employees,
            "search_query": search_query,
            "selected_department": department,
            "selected_role": role,
            "selected_status": status,
            "departments": EmployeeProfile.DEPARTMENT_CHOICES,
            "roles": valid_roles,
            "can_manage_employees": (
                request.user.is_authenticated
                and (
                    request.user.is_superuser
                    or request.user.groups.filter(
                        name="Administrator"
                    ).exists()
                )
            ),
        },
    )


@login_required
@role_required()
@require_http_methods(["GET", "POST"])
def employee_create(request):
    if request.method == "POST":
        form = EmployeeForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            try:
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=data["username"],
                        email=data["email"],
                        first_name=data["first_name"],
                        last_name=data["last_name"],
                        password=data["password"],
                    )

                    EmployeeProfile.objects.create(
                        user=user,
                        employee_id=data["employee_id"],
                        department=data["department"],
                        job_title=data["job_title"],
                    )

                    user.groups.add(data["role"])

                    write_audit_log(
                        request,
                        "USER_CREATED",
                        user,
                        f"Created employee account: {user.username}.",
                    )

                    write_audit_log(
                        request,
                        "ROLE_CHANGED",
                        user,
                        f"Initial role assigned: {data['role'].name}.",
                    )

                messages.success(
                    request,
                    f"Employee {user.username} created successfully.",
                )
                return redirect("accounts:employee_list")

            except Exception as exc:
                print(f"Employee creation failed: {exc!r}")
                messages.error(
                    request,
                    "Employee creation failed. Check the server terminal.",
                )
    else:
        form = EmployeeForm()

    return render(
        request,
        "accounts/employee_form.html",
        {"form": form},
    )


@login_required
@role_required()
@require_http_methods(["GET", "POST"])
def employee_edit(request, pk):
    employee = get_object_or_404(
        EmployeeProfile.objects.select_related("user"),
        pk=pk,
    )
    user = employee.user

    if request.method == "POST":
        form = EmployeeEditForm(request.POST, employee=employee)

        if form.is_valid():
            data = form.cleaned_data

            original_role = user.groups.filter(
                name__in=["Administrator", "Manager", "Employee"]
            ).first()
            original_is_active = user.is_active
            original_username = user.username

            try:
                with transaction.atomic():
                    employee.employee_id = data["employee_id"]
                    employee.department = data["department"]
                    employee.job_title = data["job_title"]
                    employee.save()

                    user.username = data["username"]
                    user.first_name = data["first_name"]
                    user.last_name = data["last_name"]
                    user.email = data["email"]
                    user.is_active = data["is_active"]
                    user.save()

                    user.groups.set([data["role"]])

                    write_audit_log(
                        request,
                        "USER_UPDATED",
                        user,
                        f"Updated employee profile for {user.username}.",
                    )

                    if (
                        original_role is None
                        or original_role.pk != data["role"].pk
                    ):
                        old_role = (
                            original_role.name
                            if original_role
                            else "None"
                        )

                        write_audit_log(
                            request,
                            "ROLE_CHANGED",
                            user,
                            f"Role changed from {old_role} "
                            f"to {data['role'].name}.",
                        )

                    if original_is_active != user.is_active:
                        action = (
                            "USER_ACTIVATED"
                            if user.is_active
                            else "USER_DEACTIVATED"
                        )

                        write_audit_log(
                            request,
                            action,
                            user,
                            f"Account status changed for {user.username}.",
                        )

                messages.success(
                    request,
                    f"Employee {user.username} updated successfully.",
                )
                return redirect("accounts:employee_list")

            except Exception as exc:
                print(f"Employee update failed: {exc!r}")
                messages.error(
                    request,
                    "Update failed. Check the server terminal.",
                )
    else:
        current_role = user.groups.filter(
            name__in=["Administrator", "Manager", "Employee"]
        ).first()

        form = EmployeeEditForm(
            employee=employee,
            initial={
                "employee_id": employee.employee_id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "department": employee.department,
                "job_title": employee.job_title,
                "role": current_role.pk if current_role else None,
                "is_active": user.is_active,
            },
        )

    return render(
        request,
        "accounts/employee_edit.html",
        {"form": form, "employee": employee},
    )


def revoke_user_sessions(user):
    """Delete active database-backed sessions belonging to a user."""
    user_id = str(user.pk)

    sessions = Session.objects.filter(
        expire_date__gt=timezone.now()
    )

    for session in sessions.iterator():
        session_data = session.get_decoded()

        if session_data.get("_auth_user_id") == user_id:
            session.delete()
            

@login_required
@require_POST
def employee_offboard(request, pk):
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.shortcuts import get_object_or_404

    User = get_user_model()
    user = get_object_or_404(User, pk=pk)

    # Prevent accidentally offboarding your own account.
    if user.pk == request.user.pk:
        messages.error(request, "You cannot offboard your own account.")
        return redirect("accounts:employee_list")

    if not user.is_active:
        messages.info(request, f"{user.username} is already inactive.")
        return redirect("accounts:employee_list")

    try:
        with transaction.atomic():
            user.is_active = False
            user.save(update_fields=["is_active"])

            # Revoke existing sessions for this user.
            revoke_user_sessions(user)

            AuditLog.objects.create(
                actor=request.user,
                target_user=user,
                action="USER_DEACTIVATED",
                details=f"Employee {user.username} was offboarded.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

        messages.success(
            request,
            f"Employee {user.username} has been offboarded."
        )
    except Exception:
        import traceback
        traceback.print_exc()
        messages.error(request, "Offboarding failed. Check the server terminal.")

    return redirect("accounts:employee_list")


@login_required
@require_POST
@role_required("Administrator")
def employee_delete(request, pk):
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.shortcuts import get_object_or_404

    User = get_user_model()
    user = get_object_or_404(User, pk=pk)

    # Prevent deleting your own account.
    if user.pk == request.user.pk:
        messages.error(request, "You cannot delete your own account.")
        return redirect("accounts:employee_list")

    # Protect superuser accounts.
    if user.is_superuser:
        messages.error(request, "Superuser accounts cannot be deleted here.")
        return redirect("accounts:employee_list")

    username = user.username

    try:
        with transaction.atomic():
            # Deleting the User normally deletes its EmployeeProfile
            # if the profile has a CASCADE relationship.
            user.delete()

            AuditLog.objects.create(
                actor=request.user,
                target_user=None,
                action="USER_DELETED",
                details=f"User {username} was permanently deleted.",
                ip_address=request.META.get("REMOTE_ADDR"),
            )

        messages.success(
            request,
            f"User {username} was permanently deleted."
        )
    except Exception:
        import traceback
        traceback.print_exc()
        messages.error(
            request,
            "User deletion failed. Check the server terminal."
        )

    return redirect("accounts:employee_list")


@login_required
@role_required("Administrator")
@require_POST
def employee_reactivate(request, user_id):
    from django.contrib.auth.models import User
    from django.shortcuts import get_object_or_404

    user = get_object_or_404(User, pk=user_id)

    if user.is_active:
        messages.info(
            request,
            f"Employee {user.username} is already active.",
        )
        return redirect("accounts:employee_list")

    user.is_active = True
    user.save(update_fields=["is_active"])

    AuditLog.objects.create(
        actor=request.user,
        target_user=user,
        action="USER_ACTIVATED",
        details=f"Employee {user.username} was reactivated.",
        ip_address=request.META.get("REMOTE_ADDR"),
    )

    messages.success(
        request,
        f"Employee {user.username} has been reactivated.",
    )
    return redirect("accounts:employee_list")

@login_required
def my_profile(request):
    employee = EmployeeProfile.objects.filter(
        user=request.user
    ).first()

    return render(
        request,
        "accounts/my_profile.html",
        {"employee": employee},
    )


class DebugPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_valid(self, form):
        response = super().form_valid(form)

        # Preserve the user's current login session.
        # Record the event without logging any password values.
        try:
            write_audit_log(
                self.request,
                "PASSWORD_CHANGED",
                self.request.user,
                "User changed their own password.",
            )
        except Exception as exc:
            # Do not expose password information in diagnostic output.
            print(f"Password audit logging failed: {exc!r}")

        return response

    def form_invalid(self, form):
        return super().form_invalid(form)


@login_required
@role_required()
def audit_log_list(request):
    logs = AuditLog.objects.select_related(
        "actor", "target_user"
    ).order_by("-timestamp")

    search_query = request.GET.get("q", "").strip()
    selected_action = request.GET.get("action", "").strip()

    if search_query:
        logs = logs.filter(
            Q(actor__username__icontains=search_query)
            | Q(target_user__username__icontains=search_query)
            | Q(details__icontains=search_query)
            | Q(ip_address__icontains=search_query)
        )

    valid_actions = dict(AuditLog.ACTION_CHOICES)

    if selected_action in valid_actions:
        logs = logs.filter(action=selected_action)
    else:
        selected_action = ""

    paginator = Paginator(logs, 20)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "page_obj": page_obj,
        "search_query": search_query,
        "selected_action": selected_action,
        "actions": AuditLog.ACTION_CHOICES,
        "total_logs": AuditLog.objects.count(),
    }

    return render(request, "accounts/audit_logs.html", context)

@login_required
@role_required()
def ad_user_search(request):
    from accounts.ad_service import search_ad_users

    search_query = request.GET.get("q", "").strip()
    users = []
    error_message = ""

    if search_query:
        try:
            users = search_ad_users(search_query)
        except Exception:
            error_message = (
                "Unable to search Active Directory. "
                "Check the AD connection and server logs."
            )

    return render(
        request,
        "accounts/ad_user_search.html",
        {
            "search_query": search_query,
            "users": users,
            "error_message": error_message,
        },
    )

@login_required
@role_required("Administrator")
@require_http_methods(["GET", "POST"])
def ad_user_create(request):
    from accounts.ad_service import create_ad_user

    if request.method == "POST":
        form = ADUserCreateForm(request.POST)

        if form.is_valid():
            data = form.cleaned_data

            try:
                user_dn = create_ad_user(data)

                # Do not log passwords or other secrets.
                write_audit_log(
                    request,
                    "AD_USER_CREATED",
                    target_user=None,
                    details=(
                        f"Created Active Directory account "
                        f"{data['username']} at {user_dn}."
                    ),
                )

                messages.success(
                    request,
                    f"Active Directory user {data['username']} "
                    "was created and enabled successfully.",
                )
                return redirect("accounts:ad_user_search")

            except Exception as exc:
                # The exception should never include the submitted password.
                print(f"AD user creation failed: {type(exc).__name__}: {exc}")
                messages.error(
                    request,
                    "Active Directory user creation failed. "
                    "Check the server terminal and AD account status.",
                )
    else:
        form = ADUserCreateForm()

    return render(
        request,
        "accounts/ad_user_create.html",
        {"form": form},
    )
