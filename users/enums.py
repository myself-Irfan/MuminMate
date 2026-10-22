from enum import StrEnum

from django.db import models


class SessionKey(StrEnum):
    LOGIN_AT = "login_at"


class ThrottleScope(models.TextChoices):
    LOGIN_FAILURE = "login_failure"
    PASSWORD_RESET = "password_reset"  # noqa: S105 - a label, not a secret
    SIGNUP = "signup"
    VERIFICATION_EMAIL = "verification_email"
