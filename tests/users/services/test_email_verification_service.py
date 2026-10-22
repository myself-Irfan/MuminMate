import io
from unittest.mock import Mock

import pytest
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from kombu.exceptions import OperationalError
from pytest_django import DjangoCaptureOnCommitCallbacks

from tests.logging_support import events
from users.enums import ThrottleScope
from users.exceptions import InvalidVerificationLinkError
from users.models import ThrottleEvent, User
from users.services.email_verification_service import EmailVerificationService
from users.throttling import digest_email


@pytest.fixture
def verification_email_delay(monkeypatch: pytest.MonkeyPatch) -> Mock:
    delay = Mock()
    monkeypatch.setattr(
        "users.services.email_verification_service.send_verification_email.delay", delay
    )
    return delay


def test_request_verification_queues_email_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    verification_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        EmailVerificationService().request_verification(unverified_consumer_user)

    assert len(callbacks) == 1
    verification_email_delay.assert_not_called()


def test_request_verification_queues_email_for_user(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    verification_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().request_verification(unverified_consumer_user)

    verification_email_delay.assert_called_once_with(unverified_consumer_user.pk)


@pytest.mark.usefixtures("verification_email_delay")
def test_request_verification_records_verification_email(unverified_consumer_user: User) -> None:
    EmailVerificationService().request_verification(unverified_consumer_user)

    event = ThrottleEvent.objects.get()
    assert event.scope == ThrottleScope.VERIFICATION_EMAIL
    assert event.email_digest == digest_email(unverified_consumer_user.email)
    assert event.ip is None


@pytest.mark.usefixtures("request_limits")
def test_resend_queues_link_when_not_limited(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    verification_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().resend(unverified_consumer_user)

    verification_email_delay.assert_called_once_with(unverified_consumer_user.pk)
    assert ThrottleEvent.objects.filter(scope=ThrottleScope.VERIFICATION_EMAIL).count() == 1


@pytest.mark.usefixtures("request_limits")
def test_resend_skips_when_limited(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    verification_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    service = EmailVerificationService()
    with django_capture_on_commit_callbacks(execute=True):
        service.request_verification(unverified_consumer_user)
    verification_email_delay.reset_mock()

    with django_capture_on_commit_callbacks(execute=True):
        service.resend(unverified_consumer_user)

    verification_email_delay.assert_not_called()
    assert ThrottleEvent.objects.filter(scope=ThrottleScope.VERIFICATION_EMAIL).count() == 1


def test_request_verification_logs_when_email_cannot_be_queued(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    verification_email_delay: Mock,
    unverified_consumer_user: User,
) -> None:
    verification_email_delay.side_effect = OperationalError("broker unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        EmailVerificationService().request_verification(unverified_consumer_user)

    [line] = events(json_logs, "verification_email_queue_failed")
    assert (line["level"], line["user_id"]) == ("error", unverified_consumer_user.pk)


def test_is_link_valid_when_token_matches(
    unverified_consumer_user: User, uidb64: str, token: str
) -> None:
    is_valid = EmailVerificationService().is_link_valid(uidb64=uidb64, token=token)

    unverified_consumer_user.refresh_from_db()
    assert is_valid
    assert not unverified_consumer_user.is_email_verified


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
