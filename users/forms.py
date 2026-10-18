from typing import Any

import django_stubs_ext
import structlog
from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.contrib.auth import forms as auth_forms
from django.core.exceptions import ValidationError

from users.models import User
from users.services.user_service import UserService
from users.validators import validate_email_is_ascii

logger = structlog.get_logger(__name__)


# Invite: the user sets the password from the invite email.
class UserAdminCreationForm(forms.ModelForm[User]):
    class Meta:
        model = User
        fields = ("email",)


class UserAdminChangeForm(auth_forms.UserChangeForm[User]):
    class Meta:
        model = User
        fields = "__all__"


class ConsumerAuthenticationForm(auth_forms.AuthenticationForm):
    username = auth_forms.UsernameField(widget=forms.EmailInput(attrs={"autofocus": True}))

    def confirm_login_allowed(self, user: User) -> None:
        super().confirm_login_allowed(user)
        if user.is_privileged:
            logger.warning("login_refused", reason="privileged_account", user_id=user.pk)
            raise self.get_invalid_login_error()


class StaffAuthenticationForm(AdminAuthenticationForm):
    def confirm_login_allowed(self, user: User) -> None:
        # super() raises for non-staff: log first.
        if not user.is_staff:
            logger.warning("login_refused", reason="not_staff", user_id=user.pk)
        super().confirm_login_allowed(user)


# Lets SetPasswordMixin[User] run; built into Django 6.0 (d0c8f89), delete on upgrade.
django_stubs_ext.monkeypatch(extra_classes=[auth_forms.SetPasswordMixin])


class SignupForm(auth_forms.SetPasswordMixin[User], forms.Form):
    email = forms.EmailField(
        max_length=User._meta.get_field("email").max_length,
        validators=[validate_email_is_ascii],
        widget=forms.EmailInput(attrs={"autocomplete": "email", "autofocus": True}),
        error_messages={
            "email_taken": "An account with this email already exists. Log in instead."
        },
    )
    password1, password2 = auth_forms.SetPasswordMixin.create_password_fields(
        label2="Confirm password"
    )
    # Validator errors still name the exact rule; this only steers.
    password1.help_text = (
        "At least 8 characters. Avoid common passwords, numbers only, or anything like your email."
    )
    password2.help_text = ""

    def clean_email(self) -> str:
        email: str = self.cleaned_data["email"]
        user_id = UserService().get_id_by_email(email)
        if user_id is not None:
            logger.info("signup_refused", reason="email_taken", user_id=user_id)
            raise ValidationError(
                self.fields["email"].error_messages["email_taken"], code="email_taken"
            )
        return email

    def clean(self) -> dict[str, Any] | None:
        cleaned_data = super().clean()
        self.validate_passwords()
        self.validate_password_for_user(User(email=self.cleaned_data.get("email", "")))
        return cleaned_data
