import re
from unittest.mock import Mock

import pytest
from django.core import mail
from django.db import DatabaseError
from django.test import Client
from django.urls import NoReverseMatch, reverse
from pytest_django import DjangoCaptureOnCommitCallbacks
from pytest_django.asserts import assertContains, assertRedirects, assertTemplateUsed

from users.models import LoginFailure, User
from users.services.login_failure_service import LoginFailureService
from users.services.password_reset_service import PasswordResetService
from users.tasks import send_password_reset_email


@pytest.fixture(autouse=True)
def send_reset_email_inline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "users.services.password_reset_service.send_password_reset_email.delay",
        Mock(side_effect=send_password_reset_email),
    )


def request_reset_link(
    client: Client, callbacks: DjangoCaptureOnCommitCallbacks, email: str
) -> str:
    with callbacks(execute=True):
        client.post("/accounts/password-reset/", {"email": email})
    path: str
    [path] = re.findall(
        r"https?://[^/]+(/accounts/password-reset/[\w-]+/[\w-]+/)", str(mail.outbox[-1].body)
    )
    return path


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


def test_password_reset_link_sets_new_password(
    client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    consumer_user: User,
    password: str,
) -> None:
    path = request_reset_link(client, django_capture_on_commit_callbacks, consumer_user.email)
    set_password_path = client.get(path)["Location"]
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
    client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    consumer_user: User,
    password: str,
) -> None:
    LoginFailureService().record(consumer_user.email, "127.0.0.1")
    path = request_reset_link(client, django_capture_on_commit_callbacks, consumer_user.email)
    set_password_path = client.get(path)["Location"]
    new_password = password + "-new"

    client.post(set_password_path, {"new_password1": new_password, "new_password2": new_password})

    assert not LoginFailure.objects.exists()


def test_password_reset_link_works_once(
    client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    consumer_user: User,
    password: str,
) -> None:
    path = request_reset_link(client, django_capture_on_commit_callbacks, consumer_user.email)
    set_password_path = client.get(path)["Location"]
    new_password = password + "-new"
    client.post(set_password_path, {"new_password1": new_password, "new_password2": new_password})

    response = Client().get(path)

    assertTemplateUsed(response, "registration/password_reset/confirm.html")
    assertContains(response, "This reset link is invalid or has expired")


def test_password_reset_keeps_old_password_when_completion_fails(
    monkeypatch: pytest.MonkeyPatch,
    client: Client,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    consumer_user: User,
    password: str,
) -> None:
    path = request_reset_link(client, django_capture_on_commit_callbacks, consumer_user.email)
    set_password_path = client.get(path)["Location"]
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
