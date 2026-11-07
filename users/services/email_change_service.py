from functools import partial

import structlog
from django.db import transaction
from kombu.exceptions import OperationalError

from users.exceptions import EmailChangeLinkForOtherAccountError, InvalidEmailChangeLinkError
from users.models import ThrottleEvent, User
from users.services.email_verification_service import EmailVerificationService
from users.services.invite_service import InviteService
from users.services.request_limit_service import RequestLimitService
from users.services.user_service import UserService
from users.tasks import send_email_change_link, send_email_changed_notice
from users.tokens import EmailChangeSigner

logger = structlog.get_logger(__name__)


class EmailChangeService:
    # Shares the password row's count: one wrong-password limit per account.
    def record_attempt(self, user: User) -> ThrottleEvent | None:
        return RequestLimitService().record_current_password(user)

    def clear_attempt(self, attempt: ThrottleEvent) -> None:
        attempt.delete()

    def request_change(self, user: User, new_email: str) -> bool:
        if not RequestLimitService().record_email_change(user):
            return False
        logger.info("email_change_requested", user_id=user.pk)
        transaction.on_commit(partial(self._queue_change_link, user.pk, new_email))
        return True

    def get_new_email(self, user: User, token: str) -> str:
        signer = EmailChangeSigner()
        claim = signer.read_token(token)
        if claim is None:
            raise InvalidEmailChangeLinkError("This link has expired or is no longer valid.")
        if claim.user_id != user.pk:
            raise EmailChangeLinkForOtherAccountError("This link is for a different account.")
        if not signer.is_current(user, claim):
            raise InvalidEmailChangeLinkError("This link has expired or is no longer valid.")
        return claim.new_email

    def confirm(self, user: User, token: str) -> None:
        new_email = self.get_new_email(user, token)
        old_email = user.email
        if not UserService().change_email(user, new_email):
            raise InvalidEmailChangeLinkError("This link has expired or is no longer valid.")
        logger.info("email_changed", user_id=user.pk)
        transaction.on_commit(partial(self._queue_changed_notice, user.pk, old_email))

    # Invites are resent, not noticed (likely a typo); /admin/ never checks verification.
    def complete_admin_change(self, user: User, old_email: str) -> None:
        if user.is_invite_pending:
            InviteService().resend(user.pk)
            return
        transaction.on_commit(partial(self._queue_changed_notice, user.pk, old_email))
        if user.is_privileged:
            return
        EmailVerificationService().reset_verification(user)

    # A broker outage mustn't fail the request; the user can ask again.
    def _queue_change_link(self, user_id: int, new_email: str) -> None:
        try:
            send_email_change_link.delay(user_id, new_email)
        except OperationalError:
            logger.exception("email_change_link_queue_failed", user_id=user_id)

    # A broker outage mustn't fail the request; the email is already changed.
    def _queue_changed_notice(self, user_id: int, old_email: str) -> None:
        try:
            send_email_changed_notice.delay(user_id, old_email)
        except OperationalError:
            logger.exception("email_changed_notice_queue_failed", user_id=user_id)
