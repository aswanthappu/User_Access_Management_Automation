
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from . import views

app_name = "accounts"

urlpatterns = [
    path(
        "password-change/",
        views.DebugPasswordChangeView.as_view(),
        name="password_change",
    ),
    path(
        "password-change/done/",
        auth_views.PasswordChangeDoneView.as_view(
            template_name="accounts/password_change_done.html",
        ),
        name="password_change_done",
    ),
    path("audit-logs/", views.audit_log_list, name="audit_logs"),
    path("my-profile/", views.my_profile, name="my_profile"),
    path("login/", views.AppLoginView.as_view(), name="login"),
    path("logout/", views.AppLogoutView.as_view(), name="logout"),
    path("", views.dashboard, name="dashboard"),
    path("employees/", views.employee_list, name="employee_list"),
    path("employees/add/", views.employee_create, name="employee_create"),
    path(
        "employees/<int:pk>/edit/",
        views.employee_edit,
        name="employee_edit",
    ),
    path(
         "employees/<int:pk>/offboard/",
         views.employee_offboard,
         name="employee_offboard",
    ),
    path(
    "employees/<int:user_id>/reactivate/",
    views.employee_reactivate,
    name="employee_reactivate",
    ),
    
    path(
    "employees/<int:pk>/delete/",
    views.employee_delete,
    name="employee_delete",
    ),
    path("active-directory/", views.ad_user_search, name="ad_user_search"),
    path(
    "active-directory/create/",
    views.ad_user_create,
    name="ad_user_create",
    ),

]
