from datetime import date

from django.core.exceptions import ValidationError
from django.utils import timezone


# WHATWG: a valid email is ASCII; browsers send IDN domains as xn--.
def validate_email_is_ascii(value: str) -> None:
    if not value.isascii():
        raise ValidationError(
            "Use only ASCII letters, digits and symbols. "
            "For an international domain, use its xn-- form.",
            code="email_not_ascii",
        )


def validate_birth_date_not_in_future(value: date) -> None:
    if value > timezone.localdate():
        raise ValidationError("Date of birth can't be in the future.", code="birth_date_in_future")


def validate_birth_date_from_1900(value: date) -> None:
    if value < date(1900, 1, 1):
        raise ValidationError("Enter a date from 1900 onwards.", code="birth_date_too_early")
