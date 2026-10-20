from functools import partial

import structlog
from django.db import transaction
from kombu.exceptions import OperationalError

from users.models import User
from users.services.email_verification_service import EmailVerificationService
from users.services.login_failure_service import LoginFailureService
from users.services.user_service import UserService
from users.tasks import send_invite_email

logger = structlog.get_logger(__name__)


class InviteService:
    def invite(self, *, email: str) -> User:
        user = UserService().create(email=email, password=None)
        logger.info("user_invited", user_id=user.pk)
        transaction.on_commit(partial(self._queue_invite_email, user.pk))
        return user

    def resend(self, user_id: int) -> None:
        logger.info("invite_resend_requested", user_id=user_id)
        transaction.on_commit(partial(self._queue_invite_email, user_id))

    def accept(self, user: User, ip: str | None) -> None:
        EmailVerificationService().mark_verified(user)
        LoginFailureService().clear(user.email, ip)
        logger.info("invite_accepted", user_id=user.pk)

    # A broker outage mustn't fail the request, as with Django's own password reset send_mail.
    def _queue_invite_email(self, user_id: int) -> None:
        try:
            send_invite_email.delay(user_id)
        except OperationalError:
            logger.exception("invite_email_queue_failed", user_id=user_id)
