from typing import ClassVar

import structlog
from django import forms
from django.contrib.auth import forms as auth_forms

from users.models import User
from users.services.user_service import UserService

logger = structlog.get_logger(__name__)


class SignupForm(auth_forms.BaseUserCreationForm[User]):
    password1, password2 = auth_forms.SetPasswordMixin.create_password_fields(
        label2="Confirm password"
    )
    # Validator errors still name the exact rule; this only steers.
    password1.help_text = (
        "At least 8 characters. Avoid common passwords, numbers only, or anything like your email."
    )
    password2.help_text = ""

    class Meta:
        model = User
        fields = ("email",)
        widgets: ClassVar[dict[str, forms.Widget]] = {
            "email": forms.EmailInput(attrs={"autocomplete": "email"})
        }
        error_messages: ClassVar[dict[str, dict[str, str]]] = {
            "email": {"unique": "An account with this email already exists. Log in instead."}
        }

    def validate_unique(self) -> None:
        super().validate_unique()
        if self.has_error("email", "unique"):
            user_id = UserService().get_id_by_email(self.instance.email)
            logger.info("signup_refused", reason="email_taken", user_id=user_id)
