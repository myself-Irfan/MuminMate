import pytest

from users.forms.email_change_form import EmailChangeForm
from users.models import User


def email_change_form(user: User, email: str, current_password: str) -> EmailChangeForm:
    return EmailChangeForm(user, data={"email": email, "current_password": current_password})


def test_email_change_form_normalizes_new_email(consumer_user: User, password: str) -> None:
    form = email_change_form(consumer_user, " A2@Example.COM ", password)

    assert form.is_valid()
    assert form.cleaned_data["email"] == "a2@example.com"


def test_email_change_form_fails_when_email_unchanged(consumer_user: User, password: str) -> None:
    form = email_change_form(consumer_user, consumer_user.email.upper(), password)

    assert not form.is_valid()
    assert form.has_error("email", "email_unchanged")


def test_email_change_form_fails_when_email_taken(
    consumer_user: User, unverified_consumer_user: User, password: str
) -> None:
    form = email_change_form(consumer_user, unverified_consumer_user.email.upper(), password)

    assert not form.is_valid()
    assert form.has_error("email", "unique")


def test_email_change_form_fails_when_email_not_ascii(consumer_user: User, password: str) -> None:
    form = email_change_form(consumer_user, "\u0131rfan@example.com", password)

    assert not form.is_valid()
    assert form.has_error("email", "email_not_ascii")


def test_email_change_form_fails_when_current_password_wrong(consumer_user: User) -> None:
    form = email_change_form(consumer_user, "a2@example.com", "wrong-placeholder-password")

    assert not form.is_valid()
    assert form.has_error("current_password", "password_incorrect")


@pytest.mark.parametrize("field", ["email", "current_password"])
def test_email_change_form_fails_when_field_empty(
    consumer_user: User, password: str, field: str
) -> None:
    form = EmailChangeForm(
        consumer_user,
        data={"email": "a2@example.com", "current_password": password, field: ""},
    )

    assert not form.is_valid()
    assert form.has_error(field, "required")
