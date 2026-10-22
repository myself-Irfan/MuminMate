import re
from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.core import mail
from django.db import DatabaseError
from django.test import Client
from django.urls import NoReverseMatch, reverse
from pytest_django import DjangoCaptureOnCommitCallbacks
from pytest_django.asserts import assertContains, assertRedirects, assertTemplateUsed

from users.enums import ThrottleScope
from users.models import ThrottleEvent, User
from users.services.login_failure_service import LoginFailureService
from users.services.password_reset_service import PasswordResetService
from users.tasks import send_password_reset_email
from users.throttling import digest_email


@pytest.fixture(autouse=True)
def send_reset_email_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "users.services.password_reset_service.send_password_reset_email.delay",
        Mock(side_effect=send_password_reset_email),
    )


@pytest.fixture
def reset_link(
    client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    consumer_user: User,
) -> str:
    with django_capture_on_commit_callbacks(execute=True):
        client.post("/accounts/password-reset/", {"email": consumer_user.email})
    path: str
    [path] = re.findall(
        r"https?://[^/]+(/accounts/password-reset/[\w-]+/[\w-]+/)", str(mail.outbox[-1].body)
    )
    return path


@pytest.fixture
def set_password_path(client: Client, reset_link: str) -> str:
    location: str = client.get(reset_link)["Location"]
    return location


def test_password_reset_page_renders(client: Client) -> None:
    response = client.get("/accounts/password-reset/")

    assertTemplateUsed(response, "registration/password_reset/form.html")


def test_password_reset_request_redirects_to_done_for_known_email(
    client: Client, consumer_user: User
) -> None:
    response = client.post("/accounts/password-reset/", {"email": consumer_user.email})

    assertRedirects(response, "/accounts/password-reset/done/")
    assertTemplateUsed(client.get(response["Location"]), "registration/password_reset/done.html")


@pytest.mark.django_db
def test_password_reset_request_redirects_to_done_for_unknown_email(client: Client) -> None:
    response = client.post("/accounts/password-reset/", {"email": "nobody@example.com"})

    assertRedirects(response, "/accounts/password-reset/done/")
    assertTemplateUsed(client.get(response["Location"]), "registration/password_reset/done.html")


@pytest.mark.django_db
def test_password_reset_request_recorded_for_unknown_email(client: Client) -> None:
    client.post("/accounts/password-reset/", {"email": "nobody@example.com"})

    event = ThrottleEvent.objects.get()
    assert event.scope == ThrottleScope.PASSWORD_RESET
    assert event.email_digest == digest_email("nobody@example.com")


@pytest.mark.usefixtures("request_limits")
def test_password_reset_request_refused_when_limited(
    client: Client,
    consumer_user: User,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        client.post("/accounts/password-reset/", {"email": consumer_user.email})

    with django_capture_on_commit_callbacks(execute=True):
        response = client.post("/accounts/password-reset/", {"email": consumer_user.email})

    assertContains(
        response,
        "Too many reset requests for this email. Try again later.",
        status_code=HTTPStatus.TOO_MANY_REQUESTS,
    )
    assert len(mail.outbox) == 1
    assert ThrottleEvent.objects.count() == 1


def test_password_reset_link_sets_new_password(
    client: Client, consumer_user: User, password: str, set_password_path: str
) -> None:
    new_password = password + "-new"

    response = client.post(
        set_password_path, {"new_password1": new_password, "new_password2": new_password}
    )

    assertRedirects(response, "/accounts/password-reset/complete/")
    assertTemplateUsed(
        client.get(response["Location"]), "registration/password_reset/complete.html"
    )
    consumer_user.refresh_from_db()
    assert consumer_user.check_password(new_password)


def test_password_reset_clears_own_login_failures(
    client: Client, consumer_user: User, password: str, set_password_path: str
) -> None:
    LoginFailureService().record_attempt(consumer_user.email, "127.0.0.1")
    new_password = password + "-new"

    client.post(set_password_path, {"new_password1": new_password, "new_password2": new_password})

    assert not ThrottleEvent.objects.filter(scope=ThrottleScope.LOGIN_FAILURE).exists()


def test_password_reset_link_works_once(
    client: Client, password: str, reset_link: str, set_password_path: str
) -> None:
    new_password = password + "-new"
    client.post(set_password_path, {"new_password1": new_password, "new_password2": new_password})

    response = Client().get(reset_link)

    assertTemplateUsed(response, "registration/password_reset/confirm.html")
    assertContains(response, "This reset link is invalid or has expired")


def test_password_reset_keeps_old_password_when_completion_fails(
    monkeypatch: pytest.MonkeyPatch,
    client: Client,
    consumer_user: User,
    password: str,
    set_password_path: str,
) -> None:
    monkeypatch.setattr(
        PasswordResetService, "complete_reset", Mock(side_effect=DatabaseError("db gone"))
    )
    new_password = password + "-new"

    with pytest.raises(DatabaseError):
        client.post(
            set_password_path, {"new_password1": new_password, "new_password2": new_password}
        )

    consumer_user.refresh_from_db()
    assert consumer_user.check_password(password)


def test_admin_login_offers_no_password_reset() -> None:
    with pytest.raises(NoReverseMatch):
        reverse("admin_password_reset")
