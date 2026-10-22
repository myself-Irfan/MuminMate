import io
from collections.abc import Callable

import pytest
from django.contrib.auth.signals import user_logged_out
from django.test import Client, RequestFactory

from tests.logging_support import events, json_lines
from users.models import User
from users.services.login_failure_service import LoginFailureService
from users.throttling import digest_email

pytestmark = pytest.mark.usefixtures("login_limits")


@pytest.mark.parametrize(
    ("path", "user_fixture"),
    [("/accounts/login/", "consumer_user"), ("/admin/login/", "staff_user")],
)
def test_login_logged_with_user_id(
    request: pytest.FixtureRequest,
    client: Client,
    json_logs: io.StringIO,
    password: str,
    path: str,
    user_fixture: str,
) -> None:
    user: User = request.getfixturevalue(user_fixture)

    client.post(path, {"username": user.email, "password": password})

    [line] = events(json_logs, "login_succeeded")
    assert (line["level"], line["user_id"]) == ("info", user.pk)


# Upper case: the lookup must normalize like the login.
@pytest.mark.parametrize("typed", [str, str.upper])
def test_wrong_password_logged_with_user_id_when_account_exists(
    client: Client, json_logs: io.StringIO, consumer_user: User, typed: Callable[[str], str]
) -> None:
    client.post("/accounts/login/", {"username": typed(consumer_user.email), "password": "wrong"})

    [line] = events(json_logs, "login_failed")
    assert (line["level"], line["reason"], line["user_id"], line["email_digest"]) == (
        "warning",
        "bad_credentials",
        consumer_user.pk,
        digest_email(consumer_user.email),
    )


@pytest.mark.django_db
def test_unknown_email_logged_with_null_user_id(client: Client, json_logs: io.StringIO) -> None:
    client.post("/accounts/login/", {"username": "nobody@example.com", "password": "wrong"})

    [line] = events(json_logs, "login_failed")
    assert (line["reason"], line["email_digest"]) == (
        "bad_credentials",
        digest_email("nobody@example.com"),
    )
    assert line["user_id"] is None


def test_throttled_login_logged_with_null_user_id(
    client: Client, json_logs: io.StringIO, consumer_user: User, password: str
) -> None:
    LoginFailureService().record_attempt(consumer_user.email, "127.0.0.1")
    LoginFailureService().record_attempt(consumer_user.email, "127.0.0.1")

    client.post("/accounts/login/", {"username": consumer_user.email, "password": password})

    [line] = events(json_logs, "login_failed")
    assert (line["level"], line["reason"], line["email_digest"]) == (
        "warning",
        "throttled",
        digest_email(consumer_user.email),
    )
    assert line["user_id"] is None
    assert consumer_user.email not in json_logs.getvalue()
    assert password not in json_logs.getvalue()


@pytest.mark.parametrize(
    ("path", "user_fixture", "reason"),
    [
        ("/accounts/login/", "staff_user", "privileged_account"),
        ("/admin/login/", "consumer_user", "not_staff"),
    ],
)
def test_login_at_wrong_door_refused(
    request: pytest.FixtureRequest,
    client: Client,
    json_logs: io.StringIO,
    password: str,
    path: str,
    user_fixture: str,
    reason: str,
) -> None:
    user: User = request.getfixturevalue(user_fixture)

    client.post(path, {"username": user.email, "password": password})

    [line] = events(json_logs, "login_refused")
    assert (line["level"], line["reason"], line["user_id"]) == ("warning", reason, user.pk)
    assert events(json_logs, "login_succeeded") == []


@pytest.mark.parametrize(
    ("path", "user_fixture"),
    [("/accounts/logout/", "consumer_user"), ("/admin/logout/", "staff_user")],
)
def test_logout_logged_with_user_id(
    request: pytest.FixtureRequest,
    client: Client,
    json_logs: io.StringIO,
    path: str,
    user_fixture: str,
) -> None:
    user: User = request.getfixturevalue(user_fixture)
    client.force_login(user)

    client.post(path)

    [line] = events(json_logs, "logout_succeeded")
    assert (line["level"], line["user_id"]) == ("info", user.pk)


def test_logout_without_user_logged_nothing(rf: RequestFactory, json_logs: io.StringIO) -> None:
    user_logged_out.send(sender=None, request=rf.post("/accounts/logout/"), user=None)

    assert json_lines(json_logs) == []


@pytest.mark.django_db
def test_signup_logged_with_new_user_id(
    client: Client, json_logs: io.StringIO, password: str
) -> None:
    client.post(
        "/accounts/signup/",
        {"email": "new@example.com", "password1": password, "password2": password},
    )

    [line] = events(json_logs, "signup_succeeded")
    assert (line["level"], line["user_id"]) == ("info", User.objects.get().pk)


def test_signup_with_taken_email_logged_as_refused(
    client: Client, json_logs: io.StringIO, consumer_user: User, password: str
) -> None:
    client.post(
        "/accounts/signup/",
        {"email": consumer_user.email, "password1": password, "password2": password},
    )

    [line] = events(json_logs, "signup_refused")
    assert (line["level"], line["reason"], line["user_id"]) == (
        "info",
        "email_taken",
        consumer_user.pk,
    )


def test_auth_events_never_contain_email_or_password(
    client: Client, json_logs: io.StringIO, consumer_user: User, password: str
) -> None:
    wrong_guess = "wrong-password-sentinel"
    signup = {"email": consumer_user.email, "password1": password, "password2": password}

    client.post("/accounts/login/", {"username": consumer_user.email, "password": wrong_guess})
    client.post("/admin/login/", {"username": consumer_user.email, "password": password})
    client.post("/accounts/login/", {"username": consumer_user.email, "password": password})
    client.post("/accounts/logout/")
    client.post("/accounts/signup/", signup)

    logged = json_logs.getvalue()
    assert consumer_user.email not in logged
    assert password not in logged
    assert wrong_guess not in logged
