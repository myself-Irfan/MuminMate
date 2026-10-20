import structlog
from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import forms as auth_forms
from django.core.exceptions import ValidationError

from users.models import User

logger = structlog.get_logger(__name__)


class ConsumerAuthenticationForm(auth_forms.AuthenticationForm):
    username = auth_forms.UsernameField(widget=forms.EmailInput(attrs={"autofocus": True}))

    def confirm_login_allowed(self, user: User) -> None:
        super().confirm_login_allowed(user)
        self._validate_not_privileged(user)
        self._validate_email_verified(user)

    def _validate_not_privileged(self, user: User) -> None:
        if user.is_privileged:
            logger.warning("login_refused", reason="privileged_account", user_id=user.pk)
            raise self.get_invalid_login_error()

    def _validate_email_verified(self, user: User) -> None:
        if not user.is_email_verified:
            logger.warning("login_refused", reason="email_unverified", user_id=user.pk)
            raise ValidationError("Confirm your email to log in.", code="email_unverified")


class StaffAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user: User) -> None:
        # super() raises for non-staff: log first.
        if not user.is_staff:
            logger.warning("login_refused", reason="not_staff", user_id=user.pk)
        super().confirm_login_allowed(user)
