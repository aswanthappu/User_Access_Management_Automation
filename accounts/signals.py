
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver

from .models import AuditLog


def get_request_ip(request):
    """Return the request IP address when available."""
    if request is None:
        return None

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        # Only trust this header when configured by a trusted proxy.
        return forwarded_for.split(",")[0].strip()

    return request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def log_user_login(sender, request, user, **kwargs):
    AuditLog.objects.create(
        actor=user,
        target_user=user,
        action="LOGIN",
        details="User logged in successfully.",
        ip_address=get_request_ip(request),
    )


@receiver(user_logged_out)
def log_user_logout(sender, request, user, **kwargs):
    # Django can send None if the user is no longer available.
    AuditLog.objects.create(
        actor=user,
        target_user=user,
        action="LOGOUT",
        details="User logged out.",
        ip_address=get_request_ip(request),
    ) if user is not None else None
