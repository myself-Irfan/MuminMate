import time
from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.contrib.sessions.backends.base import SessionBase
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import redirect

from users.enums import SessionKey
from users.models import User


class SessionTimeoutMiddleware:
    # Throttles writes; SESSION_SAVE_EVERY_REQUEST would write on every request.
    refresh_interval_seconds = 300

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            self._apply_timeouts(request)
        return self.get_response(request)

    def _apply_timeouts(self, request: HttpRequest) -> None:
        now = int(time.time())
        if self._absolute_age_reached(request.session, now):
            logout(request)
        else:
            self._refresh_idle_expiry(request.session, now)

    def _absolute_age_reached(self, session: SessionBase, now: int) -> bool:
        login_at = session.get(SessionKey.LOGIN_AT)
        # Fail closed: a session without login_at counts as expired.
        return login_at is None or now - login_at >= settings.SESSION_ABSOLUTE_AGE

    def _refresh_idle_expiry(self, session: SessionBase, now: int) -> None:
        # Renew before expiry even when idle is shorter than the interval.
        refresh_after = min(self.refresh_interval_seconds, settings.SESSION_COOKIE_AGE // 2)
        last_refreshed = session.get(SessionKey.REFRESHED_AT, session[SessionKey.LOGIN_AT])
        if now - last_refreshed >= refresh_after:
            session[SessionKey.REFRESHED_AT] = now


class ConsumerLoginRequiredMiddleware(LoginRequiredMiddleware):
    # Exempt: they have their own auth (the admin login page, the API's 401).
    exempt_namespaces = frozenset({"admin", "api"})

    def process_view(
        self,
        request: HttpRequest,
        view_func: Callable[..., HttpResponseBase],
        view_args: tuple[Any, ...],
        view_kwargs: dict[Any, Any],
    ) -> HttpResponseBase | None:
        if self._is_exempt_url(request):
            return None
        # One cookie for the whole site: an admin login reaches these pages too.
        if isinstance(request.user, User) and request.user.is_privileged:
            return redirect("admin:index")
        return super().process_view(request, view_func, view_args, view_kwargs)

    def _is_exempt_url(self, request: HttpRequest) -> bool:
        namespaces = request.resolver_match.namespaces if request.resolver_match else []
        return any(namespace in self.exempt_namespaces for namespace in namespaces)
