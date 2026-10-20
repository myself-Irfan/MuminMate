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
def uidb64(unverified_consumer_user: User) -> str:
    return urlsafe_base64_encode(force_bytes(unverified_consumer_user.pk))


@pytest.fixture
def token(unverified_consumer_user: User) -> str:
    return EmailVerificationTokenGenerator().make_token(unverified_consumer_user)


@pytest.fixture
def signup_email_delay(monkeypatch: pytest.MonkeyPatch) -> Mock:
    delay = Mock()
    monkeypatch.setattr("users.services.email_verification_service.send_signup_email.delay", delay)
    return delay


def test_request_verification_queues_email_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        EmailVerificationService().request_verification(unverified_consumer_user.pk)

    assert len(callbacks) == 1
    signup_email_delay.assert_not_called()


def test_request_verification_queues_email_for_user(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().request_verification(unverified_consumer_user.pk)

    signup_email_delay.assert_called_once_with(unverified_consumer_user.pk)


def test_request_verification_logs_when_email_cannot_be_queued(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    signup_email_delay.side_effect = OperationalError("broker unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().request_verification(unverified_consumer_user.pk)

    [line] = events(json_logs, "signup_email_queue_failed")
    assert (line["level"], line["user_id"]) == ("error", unverified_consumer_user.pk)


@pytest.fixture
def already_verified_email_delay(monkeypatch: pytest.MonkeyPatch) -> Mock:
    delay = Mock()
    monkeypatch.setattr(
        "users.services.email_verification_service.send_already_verified_email.delay", delay
    )
    return delay


def test_request_resend_queues_email_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        EmailVerificationService().request_resend(unverified_consumer_user.email)

    assert len(callbacks) == 1
    signup_email_delay.assert_not_called()


def test_request_resend_queues_new_link_when_unverified(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    already_verified_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().request_resend(f" {unverified_consumer_user.email.upper()} ")

    signup_email_delay.assert_called_once_with(unverified_consumer_user.pk)
    already_verified_email_delay.assert_not_called()


def test_request_resend_queues_already_verified_email_when_verified(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    already_verified_email_delay: Mock,
    consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().request_resend(consumer_user.email)

    already_verified_email_delay.assert_called_once_with(consumer_user.pk)
    signup_email_delay.assert_not_called()


@pytest.mark.django_db
def test_request_resend_skipped_when_email_unknown(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        EmailVerificationService().request_resend("nobody@example.com")

    assert callbacks == []
    [line] = events(json_logs, "verification_resend_skipped")
    assert (line["level"], line["user_id"]) == ("info", None)


def test_request_resend_skipped_when_user_inactive(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    unverified_consumer_user: User,
) -> None:
    unverified_consumer_user.is_active = False
    unverified_consumer_user.save()

    with django_capture_on_commit_callbacks() as callbacks:
        EmailVerificationService().request_resend(unverified_consumer_user.email)

    assert callbacks == []
    [line] = events(json_logs, "verification_resend_skipped")
    assert line["user_id"] == unverified_consumer_user.pk


def test_request_resend_skipped_when_user_privileged(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    privileged_user: User,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        EmailVerificationService().request_resend(privileged_user.email)

    assert callbacks == []
    [line] = events(json_logs, "verification_resend_skipped")
    assert line["user_id"] == privileged_user.pk


def test_request_resend_logs_when_already_verified_email_cannot_be_queued(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    already_verified_email_delay: Mock,
    consumer_user: User,
) -> None:
    already_verified_email_delay.side_effect = OperationalError("broker unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().request_resend(consumer_user.email)

    [line] = events(json_logs, "already_verified_email_queue_failed")
    assert (line["level"], line["user_id"]) == ("error", consumer_user.pk)


def test_is_link_valid_when_token_matches(
    unverified_consumer_user: User, uidb64: str, token: str
) -> None:
    is_valid = EmailVerificationService().is_link_valid(uidb64=uidb64, token=token)

    unverified_consumer_user.refresh_from_db()
    assert is_valid
    assert not unverified_consumer_user.is_email_verified


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


def test_verify_marks_user_verified(
    unverified_consumer_user: User, uidb64: str, token: str
) -> None:
    EmailVerificationService().verify(uidb64=uidb64, token=token)

    unverified_consumer_user.refresh_from_db()
    assert unverified_consumer_user.is_email_verified


def test_mark_verified_verifies_unverified_user(unverified_consumer_user: User) -> None:
    was_marked = EmailVerificationService().mark_verified(unverified_consumer_user)

    unverified_consumer_user.refresh_from_db()
    assert was_marked
    assert unverified_consumer_user.is_email_verified


def test_mark_verified_keeps_first_timestamp_when_already_verified(
    unverified_consumer_user: User,
) -> None:
    verification = EmailVerificationService()
    verification.mark_verified(unverified_consumer_user)
    unverified_consumer_user.refresh_from_db()
    first_verified_at = unverified_consumer_user.email_verified_at

    was_marked = verification.mark_verified(unverified_consumer_user)

    unverified_consumer_user.refresh_from_db()
    assert not was_marked
    assert unverified_consumer_user.email_verified_at == first_verified_at


def test_mark_verified_logs_only_first_time(
    json_logs: io.StringIO, unverified_consumer_user: User
) -> None:
    verification = EmailVerificationService()

    verification.mark_verified(unverified_consumer_user)
    verification.mark_verified(unverified_consumer_user)

    [line] = events(json_logs, "email_verified")
    assert line["user_id"] == unverified_consumer_user.pk


def test_verify_raises_when_link_used_twice(
    unverified_consumer_user: User, uidb64: str, token: str
) -> None:
    verification = EmailVerificationService()
    verification.verify(uidb64=uidb64, token=token)
    unverified_consumer_user.refresh_from_db()
    first_verified_at = unverified_consumer_user.email_verified_at

    with pytest.raises(InvalidVerificationLinkError):
        verification.verify(uidb64=uidb64, token=token)

    unverified_consumer_user.refresh_from_db()
    assert unverified_consumer_user.email_verified_at == first_verified_at


def test_verify_raises_when_token_for_another_user(
    unverified_consumer_user: User, staff_user: User, uidb64: str
) -> None:
    staff_token = EmailVerificationTokenGenerator().make_token(staff_user)

    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64=uidb64, token=staff_token)

    unverified_consumer_user.refresh_from_db()
    assert not unverified_consumer_user.is_email_verified


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
    unverified_consumer_user: User, uidb64: str, token: str
) -> None:
    unverified_consumer_user.is_active = False
    unverified_consumer_user.save()

    assert not EmailVerificationService().is_link_valid(uidb64=uidb64, token=token)


def test_verify_logs_email_verified(
    json_logs: io.StringIO, unverified_consumer_user: User, uidb64: str, token: str
) -> None:
    EmailVerificationService().verify(uidb64=uidb64, token=token)

    [line] = events(json_logs, "email_verified")
    assert (line["level"], line["user_id"]) == ("info", unverified_consumer_user.pk)


def test_refused_link_logged_without_user_id(json_logs: io.StringIO, token: str) -> None:
    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64="a", token=token)

    [line] = events(json_logs, "email_verification_refused")
    assert (line["level"], line["user_id"]) == ("warning", None)


# Another request verified the user between our check and our write.
def test_verify_raises_when_verified_concurrently(
    monkeypatch: pytest.MonkeyPatch, unverified_consumer_user: User, uidb64: str, token: str
) -> None:
    stale = User.objects.get(pk=unverified_consumer_user.pk)
    User.objects.filter(pk=unverified_consumer_user.pk).update(email_verified_at=timezone.now())
    monkeypatch.setattr(EmailVerificationService, "_get_user_by_link", Mock(return_value=stale))

    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64=uidb64, token=token)


def test_verify_raises_when_token_expired(
    monkeypatch: pytest.MonkeyPatch, settings: Settings, unverified_consumer_user: User, uidb64: str
) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 600
    issued_at = datetime(2026, 10, 12, 12, 0)
    clock = Mock(return_value=issued_at)
    monkeypatch.setattr(EmailVerificationTokenGenerator, "_now", clock)
    expired_token = EmailVerificationTokenGenerator().make_token(unverified_consumer_user)
    clock.return_value = issued_at + timedelta(seconds=601)

    with pytest.raises(InvalidVerificationLinkError):
        EmailVerificationService().verify(uidb64=uidb64, token=expired_token)

    unverified_consumer_user.refresh_from_db()
    assert not unverified_consumer_user.is_email_verified
