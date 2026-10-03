from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.auth.backends import ModelBackend
from django.http import HttpRequest

from users.models import User
from users.services.login_failure_service import LoginFailureService


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
        # Refuse before super(): no Argon2 hash, nothing recorded.
        if failures.is_throttled(username, ip):
            return None
        user = super().authenticate(request, username=username, password=password)
        if user is None:
            failures.record(username, ip)
        else:
            failures.clear(username, ip)
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
