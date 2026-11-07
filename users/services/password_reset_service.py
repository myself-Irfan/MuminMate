from functools import partial

import structlog
from django.db import transaction
from kombu.exceptions import OperationalError

from users.models import User
from users.services.email_verification_service import EmailVerificationService
from users.services.login_failure_service import LoginFailureService
from users.services.request_limit_service import RequestLimitService
from users.tasks import send_password_reset_email

logger = structlog.get_logger(__name__)


class PasswordResetService:
    def request_reset(self, user_id: int) -> None:
        logger.info("password_reset_requested", user_id=user_id)
        transaction.on_commit(partial(self._queue_reset_email, user_id))

    def complete_reset(self, user: User, ip: str | None) -> None:
        EmailVerificationService().mark_verified(user)
        LoginFailureService().clear(user.email, ip)
        # The reset proved the inbox: the Settings rows work again at once.
        RequestLimitService().clear_current_password_failures(user)
        logger.info("password_reset_completed", user_id=user.pk)

    # A broker outage mustn't fail the request, as with Django's own password reset send_mail.
    def _queue_reset_email(self, user_id: int) -> None:
        try:
            send_password_reset_email.delay(user_id)
        except OperationalError:
            logger.exception("password_reset_email_queue_failed", user_id=user_id)
