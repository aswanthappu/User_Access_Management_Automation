
import time

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse


class SessionIdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            now = time.time()
            last_activity = request.session.get("last_activity")

            if last_activity and now - last_activity > 1800:
                logout(request)
                return redirect(reverse("accounts:login"))

            request.session["last_activity"] = now

        return self.get_response(request)
