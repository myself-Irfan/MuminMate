from enum import StrEnum

from django.db import models


class SessionKey(StrEnum):
    LOGIN_AT = "login_at"


class ThrottleScope(models.TextChoices):
    LOGIN_FAILURE = "login_failure"
    PASSWORD_RESET = "password_reset"  # noqa: S105 - a label, not a secret
    SIGNUP = "signup"
    VERIFICATION_EMAIL = "verification_email"
    CURRENT_PASSWORD_FAILURE = "current_password_failure"  # noqa: S105 - a label, not a secret
    EMAIL_CHANGE = "email_change"


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"


class EmploymentStatus(models.TextChoices):
    EMPLOYED = "employed", "Working for an employer"
    SELF_EMPLOYED = "self_employed", "Self-employed or own business"
    STUDYING = "studying", "Studying"
    OUT_OF_WORK = "out_of_work", "Out of work"
    HOMEMAKER = "homemaker", "Homemaker or caring for family"
    ILL_OR_DISABLED = "ill_or_disabled", "Not working due to illness or disability"
    RETIRED = "retired", "Retired"
    OTHER = "other", "Other"
