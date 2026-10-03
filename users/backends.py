from typing import Any

from asgiref.sync import sync_to_async
from django.contrib.auth.backends import ModelBackend
from django.http import HttpRequest

from users.models import User
from users.selectors import is_login_throttled
from users.services import clear_login_failures, record_login_failure


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
        # Refuse before super(): no Argon2 hash, nothing recorded.
        if is_login_throttled(username, ip):
            return None
        user = super().authenticate(request, username=username, password=password)
        if user is None:
            record_login_failure(username, ip)
        else:
            clear_login_failures(username, ip)
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
