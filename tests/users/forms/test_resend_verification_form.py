import pytest

from users.forms.resend_verification_form import ResendVerificationForm


def resend_form(email: str) -> ResendVerificationForm:
    return ResendVerificationForm(data={"email": email})


def test_resend_verification_form_valid_when_email_valid() -> None:
    assert resend_form("irfan@example.com").is_valid()


def test_resend_verification_form_fails_when_email_invalid() -> None:
    form = resend_form("not-an-email")

    assert not form.is_valid()
    assert form.has_error("email", "invalid")


@pytest.mark.parametrize(
    "email", ["\u0131rfan@example.com", "irfan@m\u00fcnchen.de"], ids=["dotless_i", "idn_domain"]
)
def test_resend_verification_form_fails_when_email_not_ascii(email: str) -> None:
    form = resend_form(email)

    assert not form.is_valid()
    assert form.has_error("email", "email_not_ascii")


def test_resend_verification_form_fails_when_email_longer_than_model_allows() -> None:
    form = resend_form("a" * 64 + "@" + ".".join(["b" * 60] * 4) + ".com")

    assert not form.is_valid()
    assert form.has_error("email", "max_length")
