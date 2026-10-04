import pytest
from django.contrib.auth import password_validation

from users.forms import SignupForm
from users.models import User


def signup_form(email: str, password1: str, password2: str | None = None) -> SignupForm:
    return SignupForm(
        data={"email": email, "password1": password1, "password2": password2 or password1}
    )


def test_signup_form_valid_when_input_valid(password: str) -> None:
    assert signup_form("irfan@example.com", password).is_valid()


# Enumeration guard: taken must look like new.
def test_signup_form_valid_when_email_taken(consumer_user: User, password: str) -> None:
    assert signup_form(consumer_user.email.upper(), password).is_valid()


def test_signup_form_fails_when_passwords_differ(password: str) -> None:
    form = signup_form("irfan@example.com", password, password + "-other")

    assert not form.is_valid()
    assert form.has_error("password2", "password_mismatch")


def test_signup_form_fails_when_password_too_short(short_password: str) -> None:
    form = signup_form("irfan@example.com", short_password)

    assert not form.is_valid()
    assert form.has_error("password2", "password_too_short")


def test_signup_form_fails_when_password_similar_to_email() -> None:
    form = signup_form("irfan.ahmed@example.com", "irfan-example")

    assert not form.is_valid()
    assert form.has_error("password2", "password_too_similar")


def test_signup_form_fails_when_email_invalid(password: str) -> None:
    form = signup_form("not-an-email", password)

    assert not form.is_valid()
    assert form.has_error("email", "invalid")


# Lookalikes that pass Django's [A-Z] + IGNORECASE, and IDN domains.
@pytest.mark.parametrize(
    "email",
    [
        "\u0131rfan@example.com",
        "\u0130rfan@example.com",
        "\u017fam@example.com",
        "\u212aarim@example.com",
        "irfan@m\u00fcnchen.de",
        "irfan@a\ua7cbb.com",
    ],
    ids=[
        "dotless_i",
        "dotted_capital_i",
        "long_s",
        "kelvin_sign",
        "idn_domain",
        "unicode_16_domain",
    ],
)
def test_signup_form_fails_when_email_not_ascii(email: str, password: str) -> None:
    form = signup_form(email, password)

    assert not form.is_valid()
    assert form.has_error("email", "email_not_ascii")


def test_signup_form_valid_when_domain_punycode(password: str) -> None:
    assert signup_form("irfan@xn--mnchen-3ya.de", password).is_valid()


def test_signup_form_password_hint_states_minimum_length() -> None:
    min_length = next(
        v.min_length
        for v in password_validation.get_default_password_validators()
        if isinstance(v, password_validation.MinimumLengthValidator)
    )

    hint = str(SignupForm().fields["password1"].help_text)

    assert f"At least {min_length} characters" in hint


def test_signup_form_confirmation_field_has_label_and_no_hint() -> None:
    field = SignupForm().fields["password2"]

    assert field.label == "Confirm password"
    assert not field.help_text


def test_signup_form_fails_when_email_longer_than_model_allows(password: str) -> None:
    form = signup_form("a" * 64 + "@" + ".".join(["b" * 60] * 4) + ".com", password)

    assert not form.is_valid()
    assert form.has_error("email", "max_length")
