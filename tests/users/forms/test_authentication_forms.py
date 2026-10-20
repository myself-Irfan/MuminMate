import io

from tests.logging_support import events
from users.forms.authentication_forms import ConsumerAuthenticationForm
from users.models import User


def login_form(email: str, password: str) -> ConsumerAuthenticationForm:
    return ConsumerAuthenticationForm(data={"username": email, "password": password})


def test_consumer_login_form_valid_when_email_verified(consumer_user: User, password: str) -> None:
    assert login_form(consumer_user.email, password).is_valid()


def test_consumer_login_form_refuses_unverified_email(
    unverified_consumer_user: User, password: str
) -> None:
    form = login_form(unverified_consumer_user.email, password)

    assert not form.is_valid()
    assert form.has_error("__all__", "email_unverified")
    assert form.non_field_errors() == ["Confirm your email to log in."]


def test_consumer_login_refusal_logged_when_email_unverified(
    json_logs: io.StringIO, unverified_consumer_user: User, password: str
) -> None:
    login_form(unverified_consumer_user.email, password).is_valid()

    [line] = events(json_logs, "login_refused")
    assert (line["level"], line["reason"], line["user_id"]) == (
        "warning",
        "email_unverified",
        unverified_consumer_user.pk,
    )
