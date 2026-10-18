from datetime import timedelta

import structlog
from django.conf import settings
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.utils.timesince import timeuntil

from users.exceptions import InvalidVerificationLinkError
from users.models import User
from users.services.email_service import EmailService
from users.tokens import EmailVerificationTokenGenerator

logger = structlog.get_logger(__name__)


class EmailVerificationService:
    def send_signup_email(self, user_id: int) -> None:
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            # Deactivated, or deleted since signup: nothing to tell them.
            logger.info("signup_email_skipped", user_id=user_id)
            return
        EmailService().send(
            user=user,
            subject="Confirm your email for MuminMate",
            template_name="users/emails/verify_email",
            context={
                "verify_url": self._build_verify_url(user),
                "expiry": self._describe_link_lifetime(),
            },
        )

    def is_link_valid(self, *, uidb64: str, token: str) -> bool:
        return self._get_user_by_link(uidb64, token) is not None

    def verify(self, *, uidb64: str, token: str) -> None:
        user = self._get_user_by_link(uidb64, token)
        if user is not None:
            # Conditional update: of two simultaneous uses, only one changes the row.
            updated = User.objects.filter(pk=user.pk, email_verified_at__isnull=True).update(
                email_verified_at=timezone.now()
            )
            if updated:
                logger.info("email_verified", user_id=user.pk)
                return
        logger.warning("email_verification_refused", user_id=None)
        raise InvalidVerificationLinkError("Invalid or expired verification link.")

    def _build_verify_url(self, user: User) -> str:
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = EmailVerificationTokenGenerator().make_token(user)
        path = reverse("verify_email", kwargs={"uidb64": uidb64, "token": token})
        return f"{settings.PUBLIC_URL}{path}"

    # Same instant on both sides: a later now would read "2 days, 23 hours".
    def _describe_link_lifetime(self) -> str:
        now = timezone.now()
        return timeuntil(now + timedelta(seconds=settings.PASSWORD_RESET_TIMEOUT), now=now)

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
