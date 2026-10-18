
from functools import wraps

from django.contrib import messages
from django.contrib.auth import get_user_model, views as auth_views
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.views.decorators.http import require_http_methods
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import PasswordChangeView
from django.urls import reverse_lazy
from .forms import EmployeeForm, EmployeeEditForm
from .models import EmployeeProfile

User = get_user_model()


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
        employees = employees.filter(user__groups__name=role).distinct()
    else:
        role = ""

    status = request.GET.get("status", "").strip().lower()

    if status == "active":
        employees = employees.filter(user__is_active=True)
    elif status == "inactive":
        employees = employees.filter(user__is_active=False)
    else:
        status = ""

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



@login_required
def my_profile(request):
    employee = EmployeeProfile.objects.filter(
        user=request.user
    ).first()

    if employee is None:
        return render(
            request,
            "accounts/my_profile.html",
            {"employee": None},
        )

    return render(
        request,
        "accounts/my_profile.html",
        {"employee": employee},
    )
class DebugPasswordChangeView(PasswordChangeView):
    template_name = "accounts/password_change.html"
    success_url = reverse_lazy("accounts:password_change_done")

    def form_invalid(self, form):
        password1 = form.data.get("new_password1", "")
        password2 = form.data.get("new_password2", "")

        print("Password change diagnostic:")
        print("New password field present:", bool(password1))
        print("Confirmation field present:", bool(password2))
        print("Both fields match:", password1 == password2)

        return super().form_invalid(form)

