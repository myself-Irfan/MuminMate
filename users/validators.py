from django.core.exceptions import ValidationError


# WHATWG: a valid email is ASCII; browsers send IDN domains as xn--.
def validate_email_is_ascii(value: str) -> None:
    if not value.isascii():
        raise ValidationError(
            "Use only ASCII letters, digits and symbols. "
            "For an international domain, use its xn-- form.",
            code="email_not_ascii",
        )
