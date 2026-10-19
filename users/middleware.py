import time
from collections.abc import Callable
from typing import Any

import structlog
from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.middleware import LoginRequiredMiddleware
from django.http import HttpRequest, HttpResponse, HttpResponseBase
from django.shortcuts import redirect

from users.enums import SessionKey
from users.models import User

logger = structlog.get_logger(__name__)


# The absolute timeout; Django has none. The idle one is SESSION_SAVE_EVERY_REQUEST's.
class SessionTimeoutMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            self._apply_absolute_timeout(request)
        return self.get_response(request)

    def _apply_absolute_timeout(self, request: HttpRequest) -> None:
        login_at = request.session.get(SessionKey.LOGIN_AT)
        # Fail closed: a session without login_at counts as expired.
        if login_at is None:
            logger.warning("session_expired", reason="login_time_missing", user_id=request.user.pk)
            logout(request)
            return
        session_age = int(time.time()) - login_at
        if session_age >= settings.SESSION_ABSOLUTE_AGE:
            logger.info(
                "session_expired",
                reason="absolute_age",
                user_id=request.user.pk,
                session_age_seconds=session_age,
            )
            logout(request)


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
