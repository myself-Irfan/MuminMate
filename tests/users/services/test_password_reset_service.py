import io
import re

import pytest
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from pytest_django import Settings

from tests.logging_support import events
from users.models import LoginFailure, User
from users.services.login_failure_service import LoginFailureService
from users.services.password_reset_service import PasswordResetService


@pytest.fixture
def public_url(settings: Settings) -> str:
    url = "https://muminmate.example"
    settings.PUBLIC_URL = url
    return url


def test_reset_email_sends_reset_link(consumer_user: User, public_url: str) -> None:
    PasswordResetService().send_reset_email(consumer_user.pk)

    [sent] = mail.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    assert sent.to == [consumer_user.email]
    assert sent.subject == "Reset your MuminMate password"
    [link] = re.findall(
        rf"{re.escape(public_url)}/accounts/password-reset/[\w-]+/[\w-]+/", str(sent.body)
    )
    [(html, _)] = sent.alternatives
    assert isinstance(html, str)
    assert link in html


def test_reset_email_token_valid_for_user(consumer_user: User, public_url: str) -> None:
    PasswordResetService().send_reset_email(consumer_user.pk)
    [(uidb64, token)] = re.findall(
        r"/accounts/password-reset/([\w-]+)/([\w-]+)/", str(mail.outbox[0].body)
    )

    assert force_str(urlsafe_base64_decode(uidb64)) == str(consumer_user.pk)
    assert default_token_generator.check_token(consumer_user, token)


def test_reset_email_states_link_expiry(settings: Settings, consumer_user: User) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 600

    PasswordResetService().send_reset_email(consumer_user.pk)

    [sent] = mail.outbox
    assert "expires in 10\xa0minutes" in sent.body


def test_reset_email_skipped_when_user_inactive(
    json_logs: io.StringIO, consumer_user: User
) -> None:
    consumer_user.is_active = False
    consumer_user.save()

    PasswordResetService().send_reset_email(consumer_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "password_reset_email_skipped")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)


def test_reset_email_skipped_when_password_unusable(
    json_logs: io.StringIO, consumer_user: User
) -> None:
    consumer_user.set_unusable_password()
    consumer_user.save()

    PasswordResetService().send_reset_email(consumer_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "password_reset_email_skipped")
    assert line["user_id"] == consumer_user.pk


def test_reset_email_skipped_when_user_privileged(json_logs: io.StringIO, staff_user: User) -> None:
    PasswordResetService().send_reset_email(staff_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "password_reset_email_skipped")
    assert line["user_id"] == staff_user.pk


@pytest.mark.django_db
def test_reset_email_skipped_when_user_deleted(json_logs: io.StringIO) -> None:
    PasswordResetService().send_reset_email(999_999)

    assert mail.outbox == []
    [line] = events(json_logs, "password_reset_email_skipped")
    assert line["user_id"] == 999_999


def test_complete_reset_verifies_email(consumer_user: User) -> None:
    PasswordResetService().complete_reset(consumer_user, "198.51.100.1")

    consumer_user.refresh_from_db()
    assert consumer_user.is_email_verified


def test_complete_reset_clears_own_failures_only(consumer_user: User) -> None:
    failures = LoginFailureService()
    failures.record(consumer_user.email, "198.51.100.1")
    failures.record(consumer_user.email, "203.0.113.7")

    PasswordResetService().complete_reset(consumer_user, "198.51.100.1")

    assert list(LoginFailure.objects.values_list("ip", flat=True)) == ["203.0.113.7"]


def test_complete_reset_logs_completed(json_logs: io.StringIO, consumer_user: User) -> None:
    PasswordResetService().complete_reset(consumer_user, None)

    [line] = events(json_logs, "password_reset_completed")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)
