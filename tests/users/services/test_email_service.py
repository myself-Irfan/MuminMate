import io
import re
from smtplib import SMTPRecipientsRefused
from unittest.mock import Mock

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import Client
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from pytest_django import Settings

from tests.logging_support import events
from users.models import User
from users.services.email_service import EmailService
from users.tokens import ConsumerPasswordResetTokenGenerator, InviteTokenGenerator


@pytest.fixture
def public_url(settings: Settings) -> str:
    url = "https://muminmate.example"
    settings.PUBLIC_URL = url
    return url


def test_verification_email_sends_verify_link(
    settings: Settings, unverified_consumer_user: User, public_url: str
) -> None:
    settings.DEFAULT_FROM_EMAIL = "MuminMate <no-reply@example.com>"

    EmailService().send_verification_email(unverified_consumer_user.pk)

    [sent] = mail.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    assert sent.to == [unverified_consumer_user.email]
    assert sent.from_email == "MuminMate <no-reply@example.com>"
    assert sent.subject == "Confirm your email for MuminMate"
    [link] = re.findall(rf"{re.escape(public_url)}/accounts/verify/[\w-]+/[\w-]+/", str(sent.body))
    [(html, mimetype)] = sent.alternatives
    assert isinstance(html, str)
    assert link in html
    assert mimetype == "text/html"


def test_verification_email_link_verifies_user(
    client: Client, unverified_consumer_user: User, public_url: str
) -> None:
    EmailService().send_verification_email(unverified_consumer_user.pk)
    [path] = re.findall(
        rf"{re.escape(public_url)}(/accounts/verify/[\w-]+/[\w-]+/)", str(mail.outbox[0].body)
    )

    client.post(path)

    unverified_consumer_user.refresh_from_db()
    assert unverified_consumer_user.is_email_verified


@pytest.mark.parametrize(
    ("timeout_seconds", "expiry"), [(259_200, "3\xa0days"), (600, "10\xa0minutes")]
)
def test_verification_email_states_link_expiry(
    settings: Settings, unverified_consumer_user: User, timeout_seconds: int, expiry: str
) -> None:
    settings.PASSWORD_RESET_TIMEOUT = timeout_seconds

    EmailService().send_verification_email(unverified_consumer_user.pk)

    [sent] = mail.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    [(html, _)] = sent.alternatives
    assert isinstance(html, str)
    assert f"expires in {expiry}" in sent.body
    assert f"expires in {expiry}" in html


def test_verification_email_skipped_when_user_inactive(
    json_logs: io.StringIO, unverified_consumer_user: User
) -> None:
    unverified_consumer_user.is_active = False
    unverified_consumer_user.save()

    EmailService().send_verification_email(unverified_consumer_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "verification_email_skipped")
    assert (line["level"], line["user_id"]) == ("info", unverified_consumer_user.pk)


# Confirmed between queueing and sending: the link would already be dead.
def test_verification_email_skipped_when_user_already_verified(
    json_logs: io.StringIO, consumer_user: User
) -> None:
    EmailService().send_verification_email(consumer_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "verification_email_skipped")
    assert line["user_id"] == consumer_user.pk


@pytest.mark.django_db
def test_verification_email_skipped_when_user_deleted(json_logs: io.StringIO) -> None:
    EmailService().send_verification_email(999_999)

    assert mail.outbox == []
    [line] = events(json_logs, "verification_email_skipped")
    assert line["user_id"] == 999_999


def test_password_reset_email_sends_reset_link(consumer_user: User, public_url: str) -> None:
    EmailService().send_password_reset_email(consumer_user.pk)

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


def test_password_reset_email_token_valid_for_user(consumer_user: User, public_url: str) -> None:
    EmailService().send_password_reset_email(consumer_user.pk)
    [(uidb64, token)] = re.findall(
        r"/accounts/password-reset/([\w-]+)/([\w-]+)/", str(mail.outbox[0].body)
    )

    assert force_str(urlsafe_base64_decode(uidb64)) == str(consumer_user.pk)
    assert ConsumerPasswordResetTokenGenerator().check_token(consumer_user, token)


def test_password_reset_email_states_link_expiry(settings: Settings, consumer_user: User) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 600

    EmailService().send_password_reset_email(consumer_user.pk)

    [sent] = mail.outbox
    assert "expires in 10\xa0minutes" in sent.body


def test_password_reset_email_skipped_when_user_inactive(
    json_logs: io.StringIO, consumer_user: User
) -> None:
    consumer_user.is_active = False
    consumer_user.save()

    EmailService().send_password_reset_email(consumer_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "password_reset_email_skipped")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)


def test_password_reset_email_skipped_when_password_unusable(
    json_logs: io.StringIO, consumer_user: User
) -> None:
    consumer_user.set_unusable_password()
    consumer_user.save()

    EmailService().send_password_reset_email(consumer_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "password_reset_email_skipped")
    assert line["user_id"] == consumer_user.pk


def test_password_reset_email_skipped_when_user_privileged(
    json_logs: io.StringIO, staff_user: User
) -> None:
    EmailService().send_password_reset_email(staff_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "password_reset_email_skipped")
    assert line["user_id"] == staff_user.pk


@pytest.mark.django_db
def test_password_reset_email_skipped_when_user_deleted(json_logs: io.StringIO) -> None:
    EmailService().send_password_reset_email(999_999)

    assert mail.outbox == []
    [line] = events(json_logs, "password_reset_email_skipped")
    assert line["user_id"] == 999_999


def test_invite_email_sends_set_password_link(invited_user: User, public_url: str) -> None:
    EmailService().send_invite_email(invited_user.pk)

    [sent] = mail.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    assert sent.to == [invited_user.email]
    assert sent.subject == "You're invited to MuminMate"
    [link] = re.findall(rf"{re.escape(public_url)}/accounts/invite/[\w-]+/[\w-]+/", str(sent.body))
    [(html, _)] = sent.alternatives
    assert isinstance(html, str)
    assert link in html


def test_invite_email_token_valid_for_user(invited_user: User, public_url: str) -> None:
    EmailService().send_invite_email(invited_user.pk)
    [(uidb64, token)] = re.findall(r"/accounts/invite/([\w-]+)/([\w-]+)/", str(mail.outbox[0].body))

    assert force_str(urlsafe_base64_decode(uidb64)) == str(invited_user.pk)
    assert InviteTokenGenerator().check_token(invited_user, token)


def test_invite_email_token_not_a_password_reset_token(invited_user: User) -> None:
    EmailService().send_invite_email(invited_user.pk)
    [token] = re.findall(r"/accounts/invite/[\w-]+/([\w-]+)/", str(mail.outbox[0].body))

    assert not ConsumerPasswordResetTokenGenerator().check_token(invited_user, token)


def test_invite_email_states_link_expiry(settings: Settings, invited_user: User) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 600

    EmailService().send_invite_email(invited_user.pk)

    [sent] = mail.outbox
    assert "expires in 10\xa0minutes" in sent.body


# Role-free: staff are invited the same way.
def test_invite_email_sent_to_invited_staff(invited_user: User) -> None:
    User.objects.filter(pk=invited_user.pk).update(is_staff=True)

    EmailService().send_invite_email(invited_user.pk)

    [sent] = mail.outbox
    assert sent.to == [invited_user.email]


def test_invite_email_skipped_when_password_set(
    json_logs: io.StringIO, consumer_user: User
) -> None:
    EmailService().send_invite_email(consumer_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "invite_email_skipped")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)


def test_invite_email_skipped_when_user_inactive(
    json_logs: io.StringIO, invited_user: User
) -> None:
    invited_user.is_active = False
    invited_user.save()

    EmailService().send_invite_email(invited_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "invite_email_skipped")
    assert line["user_id"] == invited_user.pk


@pytest.mark.django_db
def test_invite_email_skipped_when_user_deleted(json_logs: io.StringIO) -> None:
    EmailService().send_invite_email(999_999)

    assert mail.outbox == []
    [line] = events(json_logs, "invite_email_skipped")
    assert line["user_id"] == 999_999


# The task retries on OSError: a failed send must reach it.
@pytest.mark.parametrize(
    "error",
    [
        SMTPRecipientsRefused({"user@example.com": (550, b"No such user")}),
        ConnectionRefusedError(),
        TimeoutError(),
    ],
    ids=["refused", "server_down", "timeout"],
)
def test_email_raises_when_mail_server_fails(
    monkeypatch: pytest.MonkeyPatch, unverified_consumer_user: User, error: OSError
) -> None:
    monkeypatch.setattr(EmailMultiAlternatives, "send", Mock(side_effect=error))

    with pytest.raises(type(error)):
        EmailService().send_verification_email(unverified_consumer_user.pk)
