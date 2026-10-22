import io
from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.test import Client
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pytest_django.asserts import assertContains, assertRedirects

from tests.logging_support import events, json_lines
from users.models import User
from users.tokens import EmailVerificationTokenGenerator


@pytest.fixture
def verify_path(uidb64: str, token: str) -> str:
    return f"/accounts/verify/{uidb64}/{token}/"


def test_verify_page_asks_to_confirm_when_link_valid(
    client: Client, unverified_consumer_user: User, verify_path: str
) -> None:
    response = client.get(verify_path)

    unverified_consumer_user.refresh_from_db()
    assertContains(response, 'method="post"')
    assertContains(response, "Confirm my email")
    assert not unverified_consumer_user.is_email_verified


def test_verify_page_shows_invalid_when_link_invalid(
    client: Client, unverified_consumer_user: User, staff_user: User
) -> None:
    uidb64 = urlsafe_base64_encode(force_bytes(unverified_consumer_user.pk))
    staff_token = EmailVerificationTokenGenerator().make_token(staff_user)

    response = client.get(f"/accounts/verify/{uidb64}/{staff_token}/")

    assertContains(response, "This link is invalid or has expired")
    assertContains(response, 'href="/accounts/login/"')


def test_verify_confirms_and_redirects_to_login(
    client: Client, unverified_consumer_user: User, verify_path: str
) -> None:
    response = client.post(verify_path, follow=True)

    unverified_consumer_user.refresh_from_db()
    assertRedirects(response, "/accounts/login/")
    assertContains(response, "Your email is confirmed. Log in to continue.")
    assert unverified_consumer_user.is_email_verified


def test_verify_post_shows_invalid_when_link_used(
    client: Client, unverified_consumer_user: User, verify_path: str
) -> None:
    client.post(verify_path)
    unverified_consumer_user.refresh_from_db()
    first_verified_at = unverified_consumer_user.email_verified_at

    response = client.post(verify_path)

    unverified_consumer_user.refresh_from_db()
    assertContains(response, "This link is invalid or has expired")
    assert unverified_consumer_user.email_verified_at == first_verified_at


@pytest.mark.parametrize("method", ["get", "post"])
def test_verify_page_sends_referrer_only_to_same_origin(
    client: Client, verify_path: str, method: str
) -> None:
    response = getattr(client, method)(verify_path)

    assert response.headers["Referrer-Policy"] == "same-origin"


def test_verify_page_is_not_cached(client: Client, verify_path: str) -> None:
    response = client.get(verify_path)

    assert response.status_code == HTTPStatus.OK
    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.parametrize("method", ["get", "post"])
def test_verify_requests_log_no_token(
    client: Client, json_logs: io.StringIO, verify_path: str, token: str, method: str
) -> None:
    getattr(client, method)(verify_path)

    [started] = events(json_logs, "request_started")
    [finished] = events(json_logs, "request_finished")
    for line in (started, finished):
        assert token not in line["request"]
        assert "/*****/" in line["request"]


def test_csrf_failure_logs_no_token(json_logs: io.StringIO, verify_path: str, token: str) -> None:
    Client(enforce_csrf_checks=True).post(verify_path)

    [csrf] = [line for line in json_lines(json_logs) if line["logger"] == "django.security.csrf"]
    assert "/*****/" in csrf["event"]
    assert token not in json_logs.getvalue()


# django.request is silenced today; pinned in case that changes.
def test_method_not_allowed_logs_no_token(
    client: Client, json_logs: io.StringIO, verify_path: str, token: str
) -> None:
    response = client.put(verify_path)

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert token not in json_logs.getvalue()


def test_failed_verify_request_logs_no_token(
    monkeypatch: pytest.MonkeyPatch, json_logs: io.StringIO, verify_path: str, token: str
) -> None:
    monkeypatch.setattr(
        "users.views.email_verification_views.EmailVerificationService.is_link_valid",
        Mock(side_effect=RuntimeError),
    )
    Client(raise_request_exception=False).get(verify_path)

    [failed] = events(json_logs, "request_failed")
    assert token not in failed["request"]
    assert "/*****/" in failed["request"]
