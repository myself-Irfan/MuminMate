import structlog
from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from users.models import User
from users.services.email_service import EmailService
from users.services.email_verification_service import EmailVerificationService
from users.services.login_failure_service import LoginFailureService
from users.tokens import describe_token_lifetime

logger = structlog.get_logger(__name__)


class PasswordResetService:
    def send_reset_email(self, user_id: int) -> None:
        user = self._get_eligible_user(user_id)
        if user is None:
            logger.info("password_reset_email_skipped", user_id=user_id)
            return
        EmailService().send(
            user=user,
            subject="Reset your MuminMate password",
            template_name="users/emails/password_reset",
            context={"reset_url": self._build_reset_url(user), "expiry": describe_token_lifetime()},
        )

    def complete_reset(self, user: User, ip: str | None) -> None:
        EmailVerificationService().mark_verified(user)
        LoginFailureService().clear(user.email, ip)
        logger.info("password_reset_completed", user_id=user.pk)

    # The form's rules again: the user may have changed since the request.
    def _get_eligible_user(self, user_id: int) -> User | None:
        try:
            user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None
        if not user.has_usable_password() or user.is_privileged:
            return None
        return user

    def _build_reset_url(self, user: User) -> str:
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        path = reverse("password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})
        return f"{settings.PUBLIC_URL}{path}"
