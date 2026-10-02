import time
from typing import Any

from django.http import HttpRequest

from users.enums import SessionKey


# On every login: Django keeps session data when the same user logs in again.
def record_login_time(sender: object, request: HttpRequest, **kwargs: Any) -> None:
    request.session[SessionKey.LOGIN_AT] = int(time.time())
