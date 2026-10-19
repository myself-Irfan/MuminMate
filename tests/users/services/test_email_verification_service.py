import io
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from kombu.exceptions import OperationalError
from pytest_django import DjangoCaptureOnCommitCallbacks, Settings

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
def signup_email_delay(monkeypatch: pytest.MonkeyPatch) -> Mock:
    delay = Mock()
    monkeypatch.setattr("users.services.email_verification_service.send_signup_email.delay", delay)
    return delay


def test_request_verification_queues_email_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        EmailVerificationService().request_verification(consumer_user.pk)

    assert len(callbacks) == 1
    signup_email_delay.assert_not_called()


def test_request_verification_queues_email_for_user(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().request_verification(consumer_user.pk)

    signup_email_delay.assert_called_once_with(consumer_user.pk)


def test_request_verification_logs_when_email_cannot_be_queued(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    consumer_user: User,
) -> None:
    signup_email_delay.side_effect = OperationalError("broker unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().request_verification(consumer_user.pk)

    [line] = events(json_logs, "signup_email_queue_failed")
    assert (line["level"], line["user_id"]) == ("error", consumer_user.pk)


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


def test_mark_verified_verifies_unverified_user(consumer_user: User) -> None:
    was_marked = EmailVerificationService().mark_verified(consumer_user)

    consumer_user.refresh_from_db()
    assert was_marked
    assert consumer_user.is_email_verified


def test_mark_verified_keeps_first_timestamp_when_already_verified(consumer_user: User) -> None:
    verification = EmailVerificationService()
    verification.mark_verified(consumer_user)
    consumer_user.refresh_from_db()
    first_verified_at = consumer_user.email_verified_at

    was_marked = verification.mark_verified(consumer_user)

    consumer_user.refresh_from_db()
    assert not was_marked
    assert consumer_user.email_verified_at == first_verified_at


def test_mark_verified_logs_only_first_time(json_logs: io.StringIO, consumer_user: User) -> None:
    verification = EmailVerificationService()

    verification.mark_verified(consumer_user)
    verification.mark_verified(consumer_user)

    [line] = events(json_logs, "email_verified")
    assert line["user_id"] == consumer_user.pk


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
