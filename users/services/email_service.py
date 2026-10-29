import structlog
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.models import User
from users.tokens import (
    ConsumerPasswordResetTokenGenerator,
    EmailVerificationTokenGenerator,
    InviteTokenGenerator,
    describe_token_lifetime,
)

logger = structlog.get_logger(__name__)


class EmailService:
    def send_verification_email(self, user_id: int) -> None:
        user = self._get_user(user_id)
        if user is None or not user.is_verification_pending:
            logger.info("verification_email_skipped", user_id=user_id)
            return
        token = EmailVerificationTokenGenerator().make_token(user)
        self._send(
            user=user,
            subject="Confirm your email for MuminMate",
            template_name="users/emails/verify_email",
            context={
                "verify_url": self._build_link("verify_email", user, token),
            },
        )

    def send_password_reset_email(self, user_id: int) -> None:
        user = self._get_user(user_id)
        if user is None or not user.can_reset_password:
            logger.info("password_reset_email_skipped", user_id=user_id)
            return
        token = ConsumerPasswordResetTokenGenerator().make_token(user)
        self._send(
            user=user,
            subject="Reset your MuminMate password",
            template_name="users/emails/password_reset",
            context={
                "reset_url": self._build_link("password_reset_confirm", user, token),
            },
        )

    # Role-free: any account that never set a password, staff included.
    def send_invite_email(self, user_id: int) -> None:
        user = self._get_user(user_id)
        if user is None or not user.is_invite_pending:
            logger.info("invite_email_skipped", user_id=user_id)
            return
        token = InviteTokenGenerator().make_token(user)
        self._send(
            user=user,
            subject="You're invited to MuminMate",
            template_name="users/emails/invite",
            context={
                "invite_url": self._build_link("invite_confirm", user, token),
            },
        )

    def _get_user(self, user_id: int) -> User | None:
        try:
            return User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return None

    def _build_link(self, url_name: str, user: User, token: str) -> str:
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        path = reverse(url_name, kwargs={"uidb64": uidb64, "token": token})
        return f"{settings.PUBLIC_URL}{path}"

    # Every email carries a link, so each states how long it lasts.
    def _send(
        self, *, user: User, subject: str, template_name: str, context: dict[str, object]
    ) -> None:
        context = {**context, "expiry": describe_token_lifetime()}
        mail = EmailMultiAlternatives(
            subject=subject,
            body=render_to_string(f"{template_name}.txt", context),
            to=[user.email],
        )
        mail.attach_alternative(render_to_string(f"{template_name}.html", context), "text/html")
        mail.send()
