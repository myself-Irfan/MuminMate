from functools import partial

import structlog
from django.db import transaction
from kombu.exceptions import OperationalError

from users.models import ThrottleEvent, User
from users.services.request_limit_service import RequestLimitService
from users.tasks import send_password_changed_email

logger = structlog.get_logger(__name__)


class PasswordChangeService:
    def record_attempt(self, user: User) -> ThrottleEvent | None:
        return RequestLimitService().record_current_password(user)

    def clear_attempt(self, attempt: ThrottleEvent) -> None:
        attempt.delete()

    def complete_change(self, user: User) -> None:
        logger.info("password_changed", user_id=user.pk)
        transaction.on_commit(partial(self._queue_changed_email, user.pk))

    # A broker outage mustn't fail the request; the password is already changed.
    def _queue_changed_email(self, user_id: int) -> None:
        try:
            send_password_changed_email.delay(user_id)
        except OperationalError:
            logger.exception("password_changed_email_queue_failed", user_id=user_id)
