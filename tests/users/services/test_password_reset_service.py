import io
from unittest.mock import Mock

import pytest
from kombu.exceptions import OperationalError
from pytest_django import DjangoCaptureOnCommitCallbacks

from tests.logging_support import events
from users.models import LoginFailure, User
from users.services.login_failure_service import LoginFailureService
from users.services.password_reset_service import PasswordResetService


@pytest.fixture
def password_reset_email_delay(monkeypatch: pytest.MonkeyPatch) -> Mock:
    delay = Mock()
    monkeypatch.setattr(
        "users.services.password_reset_service.send_password_reset_email.delay", delay
    )
    return delay


def test_request_reset_queues_email_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    password_reset_email_delay: Mock,
    consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        PasswordResetService().request_reset(consumer_user.pk)

    assert len(callbacks) == 1
    password_reset_email_delay.assert_not_called()


def test_request_reset_queues_email_for_user(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    password_reset_email_delay: Mock,
    consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        PasswordResetService().request_reset(consumer_user.pk)

    password_reset_email_delay.assert_called_once_with(consumer_user.pk)


def test_request_reset_logs_requested(
    json_logs: io.StringIO, password_reset_email_delay: Mock, consumer_user: User
) -> None:
    PasswordResetService().request_reset(consumer_user.pk)

    [line] = events(json_logs, "password_reset_requested")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)


def test_request_reset_logs_when_email_cannot_be_queued(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    password_reset_email_delay: Mock,
    consumer_user: User,
) -> None:
    password_reset_email_delay.side_effect = OperationalError("broker unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        PasswordResetService().request_reset(consumer_user.pk)

    [line] = events(json_logs, "password_reset_email_queue_failed")
    assert (line["level"], line["user_id"]) == ("error", consumer_user.pk)


def test_complete_reset_verifies_email(unverified_consumer_user: User) -> None:
    PasswordResetService().complete_reset(unverified_consumer_user, "198.51.100.1")

    unverified_consumer_user.refresh_from_db()
    assert unverified_consumer_user.is_email_verified


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
