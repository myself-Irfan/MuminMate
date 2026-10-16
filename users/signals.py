import time
from typing import Any

import structlog
from django.db.models import Model
from django.http import HttpRequest

from users.enums import SessionKey

logger = structlog.get_logger(__name__)


# On every login: Django keeps session data when the same user logs in again.
def record_login_time(sender: object, request: HttpRequest, **kwargs: Any) -> None:
    request.session[SessionKey.LOGIN_AT] = int(time.time())


def log_login(sender: object, user: Model, **kwargs: Any) -> None:
    logger.info("login_succeeded", user_id=user.pk)


def log_logout(sender: object, user: Model | None, **kwargs: Any) -> None:
    if user is not None:
        logger.info("logout_succeeded", user_id=user.pk)
