from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.contrib.auth import SESSION_KEY
from django.test import Client
from pytest_django import DjangoCaptureOnCommitCallbacks
from pytest_django.asserts import assertContains

from users.models import User


@pytest.fixture
def login_payload(consumer_user: User, password: str) -> dict[str, str]:
    return {"username": consumer_user.email, "password": password}


@pytest.fixture
def verification_email_delay(monkeypatch: pytest.MonkeyPatch) -> Mock:
    delay = Mock()
    monkeypatch.setattr(
        "users.services.email_verification_service.send_verification_email.delay", delay
    )
    return delay


@pytest.mark.django_db
def test_login_page_title_names_page_then_site(client: Client) -> None:
    response = client.get("/accounts/login/")

    assertContains(response, "<title>Log in - MuminMate</title>", html=True)


@pytest.mark.django_db
def test_login_page_email_field_is_email_type(client: Client) -> None:
    response = client.get("/accounts/login/")

    assertContains(response, 'type="email" name="username"')


@pytest.mark.django_db
def test_login_page_links_staff_to_admin_login(client: Client) -> None:
    response = client.get("/accounts/login/")

    assertContains(response, 'href="/admin/login/"')


@pytest.mark.django_db
def test_login_page_links_to_signup(client: Client) -> None:
    response = client.get("/accounts/login/")

    assertContains(response, 'href="/accounts/signup/"')


def test_login_page_links_to_password_reset(client: Client) -> None:
    response = client.get("/accounts/login/")

    assertContains(response, 'href="/accounts/password-reset/"')


def test_login_redirects_home_when_credentials_valid(
    client: Client, consumer_user: User, login_payload: dict[str, str]
) -> None:
    response = client.post("/accounts/login/", login_payload)

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/"
    assert client.session[SESSION_KEY] == str(consumer_user.pk)


def test_login_rotates_session_key(client: Client, login_payload: dict[str, str]) -> None:
    session = client.session
    session.save()
    key_before = session.session_key

    client.post("/accounts/login/", login_payload)

    assert client.session.session_key != key_before


@pytest.mark.parametrize(
    "credentials",
    [
        {"username": "irfan@example.com", "password": "wrong-placeholder-password"},
        {"username": "nobody@example.com", "password": "placeholder-password"},
        {"username": "staff@example.com", "password": "placeholder-password"},
    ],
    ids=["wrong_password", "unknown_email", "staff_account"],
)
@pytest.mark.usefixtures("consumer_user", "staff_user")
def test_login_fails_with_same_error(client: Client, credentials: dict[str, str]) -> None:
    response = client.post("/accounts/login/", credentials)

    assert response.status_code == HTTPStatus.OK
    errors = response.context["form"].non_field_errors().as_data()
    assert [error.code for error in errors] == ["invalid_login"]
    assert SESSION_KEY not in client.session


@pytest.mark.usefixtures("request_limits")
def test_login_refused_when_unverified_sends_new_link(
    client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    verification_email_delay: Mock,
    unverified_consumer_user: User,
    password: str,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(
            "/accounts/login/", {"username": unverified_consumer_user.email, "password": password}
        )

    assertContains(response, "Confirm your email to log in. Check your inbox for the link.")
    verification_email_delay.assert_called_once_with(unverified_consumer_user.pk)
    assert SESSION_KEY not in client.session


@pytest.mark.usefixtures("request_limits")
def test_login_refused_when_unverified_sends_no_link_within_cooldown(
    client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    verification_email_delay: Mock,
    unverified_consumer_user: User,
    password: str,
) -> None:
    payload = {"username": unverified_consumer_user.email, "password": password}
    with django_capture_on_commit_callbacks(execute=True):
        client.post("/accounts/login/", payload)
        response = client.post("/accounts/login/", payload)

    assertContains(response, "Confirm your email to log in. Check your inbox for the link.")
    verification_email_delay.assert_called_once_with(unverified_consumer_user.pk)


def test_login_failure_sends_no_link(
    client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    verification_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        client.post(
            "/accounts/login/",
            {"username": unverified_consumer_user.email, "password": "wrong-placeholder-password"},
        )

    verification_email_delay.assert_not_called()


def test_login_ignores_next_on_other_host(client: Client, login_payload: dict[str, str]) -> None:
    response = client.post("/accounts/login/?next=https://evil.example/", login_payload)

    assert response["Location"] == "/"


def test_login_follows_next_on_same_host(client: Client, login_payload: dict[str, str]) -> None:
    response = client.post("/accounts/login/?next=/admin/", login_payload)

    assert response["Location"] == "/admin/"


def test_login_page_redirects_when_already_logged_in(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.get("/accounts/login/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/"


def test_logout_rejects_get(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.get("/accounts/logout/")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert SESSION_KEY in client.session


def test_logout_ends_session(client: Client, consumer_user: User) -> None:
    client.force_login(consumer_user)

    response = client.post("/accounts/logout/")

    assert response.status_code == HTTPStatus.FOUND
    assert response["Location"] == "/accounts/login/"
    assert SESSION_KEY not in client.session
