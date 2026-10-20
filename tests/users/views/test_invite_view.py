import io

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.test import Client
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pytest_django.asserts import assertContains, assertTemplateUsed

from tests.logging_support import events
from users.models import User


@pytest.fixture
def invite_path(invited_user: User) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(invited_user.pk))
    token = default_token_generator.make_token(invited_user)
    return f"/accounts/invite/{uidb64}/{token}/"


def set_password(client: Client, invite_path: str, password: str) -> str:
    set_password_path = client.get(invite_path)["Location"]
    response = client.post(
        set_password_path, {"new_password1": password, "new_password2": password}
    )
    location: str = response["Location"]
    return location


def test_invite_page_asks_to_set_password(client: Client, invite_path: str) -> None:
    response = client.get(invite_path, follow=True)

    assertTemplateUsed(response, "registration/invite/confirm.html")
    assertContains(response, "Set your password")


def test_invite_page_shows_invalid_when_token_wrong(client: Client, invited_user: User) -> None:
    uidb64 = urlsafe_base64_encode(force_bytes(invited_user.pk))

    response = client.get(f"/accounts/invite/{uidb64}/wrong-token/")

    assertTemplateUsed(response, "registration/invite/confirm.html")
    assertContains(response, "This invite link is invalid or has expired")


def test_invite_sets_password_and_verifies_email(
    client: Client, invited_user: User, invite_path: str, password: str
) -> None:
    location = set_password(client, invite_path, password)

    invited_user.refresh_from_db()
    assert invited_user.check_password(password)
    assert invited_user.is_email_verified
    assert location == "/accounts/login/"


def test_invite_sends_staff_to_admin_login(
    client: Client, invited_user: User, invite_path: str, password: str
) -> None:
    User.objects.filter(pk=invited_user.pk).update(is_staff=True)

    location = set_password(client, invite_path, password)

    assert location == "/admin/login/"


def test_invite_link_works_once(client: Client, invite_path: str, password: str) -> None:
    set_password(client, invite_path, password)

    response = client.get(invite_path, follow=True)

    assertContains(response, "This invite link is invalid or has expired")


def test_invite_confirmation_shown_after_password_set(
    client: Client, invite_path: str, password: str
) -> None:
    location = set_password(client, invite_path, password)

    response = client.get(location)

    assertContains(response, "Your password is set. Log in to continue.")


def test_invite_logged_as_accepted_not_as_reset(
    json_logs: io.StringIO, client: Client, invited_user: User, invite_path: str, password: str
) -> None:
    set_password(client, invite_path, password)

    [line] = events(json_logs, "invite_accepted")
    assert line["user_id"] == invited_user.pk
    assert events(json_logs, "password_reset_completed") == []
