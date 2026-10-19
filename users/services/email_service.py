import structlog
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.models import User
from users.tokens import EmailVerificationTokenGenerator, describe_token_lifetime

logger = structlog.get_logger(__name__)


class EmailService:
    def send_signup_email(self, user_id: int) -> None:
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            # Deactivated, or deleted since signup: nothing to tell them.
            logger.info("signup_email_skipped", user_id=user_id)
            return
        token = EmailVerificationTokenGenerator().make_token(user)
        self._send(
            user=user,
            subject="Confirm your email for MuminMate",
            template_name="users/emails/verify_email",
            context={
                "verify_url": self._build_link("verify_email", user, token),
                "expiry": describe_token_lifetime(),
            },
        )

    def send_password_reset_email(self, user_id: int) -> None:
        user = self._get_reset_eligible_user(user_id)
        if user is None:
            logger.info("password_reset_email_skipped", user_id=user_id)
            return
        token = default_token_generator.make_token(user)
        self._send(
            user=user,
            subject="Reset your MuminMate password",
            template_name="users/emails/password_reset",
            context={
                "reset_url": self._build_link("password_reset_confirm", user, token),
                "expiry": describe_token_lifetime(),
            },
        )

    # The reset form's rules again: the user may have changed since the request.
    def _get_reset_eligible_user(self, user_id: int) -> User | None:
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None
        if not user.has_usable_password() or user.is_privileged:
            return None
        return user

    def _build_link(self, url_name: str, user: User, token: str) -> str:
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        path = reverse(url_name, kwargs={"uidb64": uidb64, "token": token})
        return f"{settings.PUBLIC_URL}{path}"

    def _send(
        self, *, user: User, subject: str, template_name: str, context: dict[str, object]
    ) -> None:
        mail = EmailMultiAlternatives(
            subject=subject,
            body=render_to_string(f"{template_name}.txt", context),
            to=[user.email],
        )
        mail.attach_alternative(render_to_string(f"{template_name}.html", context), "text/html")
        mail.send()
