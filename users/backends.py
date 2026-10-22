from typing import Any

import structlog
from asgiref.sync import sync_to_async
from django.contrib.auth.backends import ModelBackend
from django.http import HttpRequest

from users.models import User
from users.services.login_failure_service import LoginFailureService
from users.services.user_service import UserService
from users.throttling import digest_email

logger = structlog.get_logger(__name__)


class ThrottledModelBackend(ModelBackend):
    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None
        ip = request.META.get("REMOTE_ADDR") if request else None
        failures = LoginFailureService()
        attempt = failures.record_attempt(username, ip)
        # Refused before super(): no Argon2 hash, nothing kept.
        if attempt is None:
            logger.warning(
                "login_failed",
                reason="throttled",
                email_digest=digest_email(username),
                user_id=None,
            )
            return None
        user = super().authenticate(request, username=username, password=password)
        if user is None:
            # The attempt stays as the failure.
            logger.warning(
                "login_failed",
                reason="bad_credentials",
                email_digest=digest_email(username),
                user_id=UserService().get_id_by_email(username),
            )
        else:
            failures.clear_attempt(attempt)
        return user

    async def aauthenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs: Any,
    ) -> User | None:
        # ModelBackend's own async version skips throttling.
        return await sync_to_async(self.authenticate)(
            request, username=username, password=password, **kwargs
        )
