import io
import re
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.test import Client
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pytest_django import Settings

from tests.logging_support import events
from users.exceptions import InvalidVerificationLinkError
from users.models import User
from users.services.email_verification_service import EmailVerificationService
from users.tokens import EmailVerificationTokenGenerator


@pytest.fixture
def uidb64(consumer_user: User) -> str:
    return urlsafe_base64_encode(force_bytes(consumer_user.pk))


@pytest.fixture
def token(consumer_user: User) -> str:
    return EmailVerificationTokenGenerator().make_token(consumer_user)


@pytest.fixture
def public_url(settings: Settings) -> str:
    url = "https://muminmate.example"
    settings.PUBLIC_URL = url
    return url


def test_signup_email_sends_verify_link(consumer_user: User, public_url: str) -> None:
    EmailVerificationService().send_signup_email(consumer_user.pk)

    [sent] = mail.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    assert sent.to == [consumer_user.email]
    assert sent.subject == "Confirm your email for MuminMate"
    [link] = re.findall(rf"{re.escape(public_url)}/accounts/verify/[\w-]+/[\w-]+/", str(sent.body))
    [(html, _)] = sent.alternatives
    assert isinstance(html, str)
    assert link in html


def test_signup_email_link_verifies_user(
    client: Client, consumer_user: User, public_url: str
) -> None:
    EmailVerificationService().send_signup_email(consumer_user.pk)
    [path] = re.findall(
        rf"{re.escape(public_url)}(/accounts/verify/[\w-]+/[\w-]+/)", str(mail.outbox[0].body)
    )

    client.post(path)

    consumer_user.refresh_from_db()
    assert consumer_user.is_email_verified


@pytest.mark.parametrize(
    ("timeout_seconds", "expiry"), [(259_200, "3\xa0days"), (600, "10\xa0minutes")]
)
def test_signup_email_states_link_expiry(
    settings: Settings, consumer_user: User, timeout_seconds: int, expiry: str
) -> None:
    settings.PASSWORD_RESET_TIMEOUT = timeout_seconds

    EmailVerificationService().send_signup_email(consumer_user.pk)

    [sent] = mail.outbox
    assert isinstance(sent, EmailMultiAlternatives)
    [(html, _)] = sent.alternatives
    assert isinstance(html, str)
    assert f"expires in {expiry}" in sent.body
    assert f"expires in {expiry}" in html


def test_is_link_valid_when_token_matches(consumer_user: User, uidb64: str, token: str) -> None:
    is_valid = EmailVerificationService().is_link_valid(uidb64=uidb64, token=token)

    consumer_user.refresh_from_db()
    assert is_valid
    assert not consumer_user.is_email_verified


def test_is_link_valid_false_when_token_for_another_user(staff_user: User, uidb64: str) -> None:
    staff_token = EmailVerificationTokenGenerator().make_token(staff_user)

    assert not EmailVerificationService().is_link_valid(uidb64=uidb64, token=staff_token)


def test_is_link_valid_false_when_uid_garbled(token: str) -> None:
    assert not EmailVerificationService().is_link_valid(uidb64="a", token=token)


def test_is_link_valid_false_once_verified(uidb64: str, token: str) -> None:
    verification = EmailVerificationService()
    verification.verify(uidb64=uidb64, token=token)

    is_valid = verification.is_link_valid(uidb64=uidb64, token=token)

    assert not is_valid


def test_verify_marks_user_verified(consumer_user: User, uidb64: str, token: str) -> None:
    EmailVerificationService().verify(uidb64=uidb64, token=token)

    consumer_user.refresh_from_db()
    assert consumer_user.is_email_verified


def test_verify_raises_when_link_used_twice(consumer_user: User, uidb64: str, token: str) -> None:
    verification = EmailVerificationService()
    verification.verify(uidb64=uidb64, token=token)
    consumer_user.refresh_from_db()
    first_verified_at = consumer_user.email_verified_at

    with pytest.raises(InvalidVerificationLinkError):
        verification.verify(uidb64=uidb64, token=token)

    consumer_user.refresh_from_db()
    assert consumer_user.email_verified_at == first_verified_at


def test_verify_raises_when_token_for_another_user(
    consumer_user: User, staff_user: User, uidb64: str
) -> None:
    staff_token = EmailVerificationTokenGenerator().make_token(staff_user)

    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64=uidb64, token=staff_token)

    consumer_user.refresh_from_db()
    assert not consumer_user.is_email_verified


@pytest.mark.parametrize(
    "garbled",
    [
        "",
        "!!!",
        "a",
        urlsafe_base64_encode(b"\xff\xfe"),
        urlsafe_base64_encode(b"not-a-number"),
        urlsafe_base64_encode(b"9" * 30),
    ],
    ids=["empty", "not_base64", "bad_padding", "not_utf8", "not_a_number", "out_of_range"],
)
def test_verify_raises_when_uid_garbled(garbled: str, token: str) -> None:
    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64=garbled, token=token)


def test_verify_raises_when_user_unknown(token: str) -> None:
    unknown_uidb64 = urlsafe_base64_encode(force_bytes(999_999))

    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64=unknown_uidb64, token=token)


def test_signup_email_skipped_when_user_inactive(
    json_logs: io.StringIO, consumer_user: User
) -> None:
    consumer_user.is_active = False
    consumer_user.save()

    EmailVerificationService().send_signup_email(consumer_user.pk)

    assert mail.outbox == []
    [line] = events(json_logs, "signup_email_skipped")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)


@pytest.mark.django_db
def test_signup_email_skipped_when_user_deleted(json_logs: io.StringIO) -> None:
    EmailVerificationService().send_signup_email(999_999)

    assert mail.outbox == []
    [line] = events(json_logs, "signup_email_skipped")
    assert line["user_id"] == 999_999


def test_is_link_valid_false_when_user_inactive(
    consumer_user: User, uidb64: str, token: str
) -> None:
    consumer_user.is_active = False
    consumer_user.save()

    assert not EmailVerificationService().is_link_valid(uidb64=uidb64, token=token)


def test_verify_logs_email_verified(
    json_logs: io.StringIO, consumer_user: User, uidb64: str, token: str
) -> None:
    EmailVerificationService().verify(uidb64=uidb64, token=token)

    [line] = events(json_logs, "email_verified")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)


def test_refused_link_logged_without_user_id(json_logs: io.StringIO, token: str) -> None:
    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64="a", token=token)

    [line] = events(json_logs, "email_verification_refused")
    assert (line["level"], line["user_id"]) == ("warning", None)


# Another request verified the user between our check and our write.
def test_verify_raises_when_verified_concurrently(
    monkeypatch: pytest.MonkeyPatch, consumer_user: User, uidb64: str, token: str
) -> None:
    stale = User.objects.get(pk=consumer_user.pk)
    User.objects.filter(pk=consumer_user.pk).update(email_verified_at=timezone.now())
    monkeypatch.setattr(EmailVerificationService, "_get_user_by_link", Mock(return_value=stale))

    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64=uidb64, token=token)


def test_verify_raises_when_token_expired(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, consumer_user: User, uidb64: str
) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 600
    issued_at = datetime(2026, 10, 12, 12, 0)
    clock = Mock(return_value=issued_at)
    monkeypatch.setattr(EmailVerificationTokenGenerator, "_now", clock)
    expired_token = EmailVerificationTokenGenerator().make_token(consumer_user)
    clock.return_value = issued_at + timedelta(seconds=601)

    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64=uidb64, token=expired_token)

    consumer_user.refresh_from_db()
    assert not consumer_user.is_email_verified
