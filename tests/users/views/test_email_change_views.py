import io
from http import HTTPStatus
from urllib.parse import quote

import pytest
from django.test import Client
from pytest_django.asserts import assertContains, assertRedirects, assertTemplateUsed

from tests.logging_support import events
from users.models import User
from users.tokens import EmailChangeSigner


@pytest.fixture
def email_change_token(consumer_user: User) -> str:
    return EmailChangeSigner().make_token(consumer_user, "new@example.com")


@pytest.fixture
def confirm_path(email_change_token: str) -> str:
    return f"/accounts/email/confirm/{email_change_token}/"


def test_confirm_page_asks_to_change_from_old_to_new_email(
    consumer_client: Client, consumer_user: User, confirm_path: str
) -> None:
    response = consumer_client.get(confirm_path)

    assertTemplateUsed(response, "users/email_change_confirm.html")
    assertContains(response, "irfan@example.com")
    assertContains(response, "new@example.com")
    assertContains(response, 'method="post"')
    assertContains(response, 'href="/accounts/settings/"')
    consumer_user.refresh_from_db()
    assert consumer_user.email == "irfan@example.com"


@pytest.mark.django_db
def test_confirm_page_sends_logged_out_user_to_login(client: Client, confirm_path: str) -> None:
    response = client.get(confirm_path)

    assertRedirects(
        response, f"/accounts/login/?next={quote(confirm_path)}", fetch_redirect_response=False
    )


@pytest.mark.usefixtures("email_changed_notice_delay")
def test_confirm_changes_email_and_returns_to_settings(
    consumer_client: Client, consumer_user: User, confirm_path: str
) -> None:
    response = consumer_client.post(confirm_path, follow=True)

    assertRedirects(response, "/accounts/settings/")
    assertContains(response, "Your email is now new@example.com.")
    consumer_user.refresh_from_db()
    assert consumer_user.email == "new@example.com"


@pytest.mark.parametrize("method", ["get", "post"])
def test_confirm_page_shows_invalid_when_token_invalid(
    consumer_client: Client, method: str
) -> None:
    response = getattr(consumer_client, method)("/accounts/email/confirm/not-a-token/")

    assertTemplateUsed(response, "users/email_change_invalid.html")
    assertContains(
        response,
        "This link has expired or is no longer valid.",
        status_code=HTTPStatus.BAD_REQUEST,
    )
    assertContains(response, 'href="/accounts/settings/"', status_code=HTTPStatus.BAD_REQUEST)


@pytest.mark.parametrize("method", ["get", "post"])
def test_confirm_page_refuses_link_for_other_account(
    client: Client,
    consumer_user: User,
    unverified_consumer_user: User,
    confirm_path: str,
    method: str,
) -> None:
    client.force_login(unverified_consumer_user)

    response = getattr(client, method)(confirm_path)

    assertContains(
        response, "This link is for a different account.", status_code=HTTPStatus.FORBIDDEN
    )
    consumer_user.refresh_from_db()
    unverified_consumer_user.refresh_from_db()
    assert (consumer_user.email, unverified_consumer_user.email) == (
        "irfan@example.com",
        "unverified@example.com",
    )


def test_confirm_refused_when_email_taken_since_sent(
    consumer_client: Client, consumer_user: User, confirm_path: str
) -> None:
    User.objects.create_user(email="new@example.com", password=None)

    response = consumer_client.post(confirm_path)

    assertContains(
        response, "That email is now used by another account.", status_code=HTTPStatus.CONFLICT
    )
    consumer_user.refresh_from_db()
    assert consumer_user.email == "irfan@example.com"


@pytest.mark.usefixtures("email_changed_notice_delay")
@pytest.mark.parametrize("method", ["get", "post"])
def test_confirm_requests_log_no_token(
    consumer_client: Client,
    json_logs: io.StringIO,
    confirm_path: str,
    email_change_token: str,
    method: str,
) -> None:
    getattr(consumer_client, method)(confirm_path)

    [started] = events(json_logs, "request_started")
    [finished] = events(json_logs, "request_finished")
    for line in (started, finished):
        assert email_change_token not in line["request"]
        assert "/*****/" in line["request"]
