from typing import Any

from django import forms
from django.core.exceptions import ValidationError

from users.models import User
from users.validators import validate_email_is_ascii


class EmailChangeForm(forms.Form):
    email = forms.EmailField(
        label="New email",
        validators=[validate_email_is_ascii],
        widget=forms.EmailInput(attrs={"autocomplete": "email"}),
    )
    current_password = forms.CharField(
        label="Current password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, user: User, *args: Any, **kwargs: Any) -> None:
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_email(self) -> str:
        email = User.objects.normalize_email(self.cleaned_data["email"])
        self._validate_email_changed(email)
        self._validate_email_available(email)
        return email

    def clean_current_password(self) -> str:
        password: str = self.cleaned_data["current_password"]
        if not self.user.check_password(password):
            raise ValidationError(
                "Your password is incorrect. Please enter it again.", code="password_incorrect"
            )
        return password

    def _validate_email_changed(self, email: str) -> None:
        if email == self.user.email:
            raise ValidationError("That's already your email.", code="email_unchanged")

    def _validate_email_available(self, email: str) -> None:
        if User.objects.filter(email=email).exists():
            raise ValidationError("That email is already in use.", code="unique")
