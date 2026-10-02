import time
from collections.abc import Callable

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.sessions.backends.base import SessionBase
from django.http import HttpRequest, HttpResponse

from users.enums import SessionKey


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
            self._renew_idle_expiry(request.session, now)

    def _absolute_age_reached(self, session: SessionBase, now: int) -> bool:
        login_at = session.get(SessionKey.LOGIN_AT)
        # Fail closed: a session without login_at counts as expired.
        return login_at is None or now - login_at >= settings.SESSION_ABSOLUTE_AGE

    def _renew_idle_expiry(self, session: SessionBase, now: int) -> None:
        # Renew before expiry even when idle is shorter than the interval.
        renew_after = min(self.refresh_interval_seconds, settings.SESSION_COOKIE_AGE // 2)
        last_renewed = session.get(SessionKey.REFRESHED_AT, session[SessionKey.LOGIN_AT])
        if now - last_renewed >= renew_after:
            session[SessionKey.REFRESHED_AT] = now
