from functools import partial

import structlog
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.http import urlsafe_base64_decode
from kombu.exceptions import OperationalError

from users.exceptions import InvalidVerificationLinkError
from users.models import User
from users.tasks import send_signup_email
from users.tokens import EmailVerificationTokenGenerator

logger = structlog.get_logger(__name__)


class EmailVerificationService:
    def request_verification(self, user_id: int) -> None:
        transaction.on_commit(partial(self._queue_signup_email, user_id))

    def is_link_valid(self, *, uidb64: str, token: str) -> bool:
        return self._get_user_by_link(uidb64, token) is not None

    def verify(self, *, uidb64: str, token: str) -> None:
        user = self._get_user_by_link(uidb64, token)
        if user is not None and self.mark_verified(user):
            return
        logger.warning("email_verification_refused", user_id=None)
        raise InvalidVerificationLinkError("Invalid or expired verification link.")

    # Conditional update: of two simultaneous calls, only one changes the row.
    def mark_verified(self, user: User) -> bool:
        updated = User.objects.filter(pk=user.pk, email_verified_at__isnull=True).update(
            email_verified_at=timezone.now()
        )
        if updated:
            logger.info("email_verified", user_id=user.pk)
        return bool(updated)

    # A broker outage mustn't fail the request, as with Django's own password reset send_mail.
    def _queue_signup_email(self, user_id: int) -> None:
        try:
            send_signup_email.delay(user_id)
        except OperationalError:
            logger.exception("signup_email_queue_failed", user_id=user_id)

    def _get_user_by_link(self, uidb64: str, token: str) -> User | None:
        user = self._get_user(uidb64)
        if user is None or not EmailVerificationTokenGenerator().check_token(user, token):
            return None
        return user

    # As Django's PasswordResetConfirmView.get_user, but active users only and narrower excepts.
    def _get_user(self, uidb64: str) -> User | None:
        try:
            pk = User._meta.pk.to_python(urlsafe_base64_decode(uidb64).decode())
            return User.objects.get(pk=pk, is_active=True)
        except (ValueError, User.DoesNotExist, ValidationError):
            return None
