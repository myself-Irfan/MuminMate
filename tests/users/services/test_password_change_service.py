import io
from unittest.mock import Mock

import pytest
from kombu.exceptions import OperationalError
from pytest_django import DjangoCaptureOnCommitCallbacks

from tests.logging_support import events
from users.enums import ThrottleScope
from users.models import ThrottleEvent, User
from users.services.password_change_service import PasswordChangeService


@pytest.mark.usefixtures("request_limits")
def test_record_attempt_saves_current_password_try_for_user(consumer_user: User) -> None:
    attempt = PasswordChangeService().record_attempt(consumer_user)

    assert attempt == ThrottleEvent.objects.get(
        scope=ThrottleScope.CURRENT_PASSWORD_FAILURE, user=consumer_user
    )


@pytest.mark.usefixtures("request_limits")
def test_record_attempt_refused_when_limit_reached(consumer_user: User) -> None:
    ThrottleEvent.objects.bulk_create(
        ThrottleEvent(scope=ThrottleScope.CURRENT_PASSWORD_FAILURE, user=consumer_user)
        for _ in range(3)
    )

    assert PasswordChangeService().record_attempt(consumer_user) is None


@pytest.mark.usefixtures("request_limits")
def test_clear_attempt_deletes_only_that_attempt(consumer_user: User) -> None:
    changes = PasswordChangeService()
    earlier = changes.record_attempt(consumer_user)
    attempt = changes.record_attempt(consumer_user)
    assert earlier is not None
    assert attempt is not None

    changes.clear_attempt(attempt)

    assert list(ThrottleEvent.objects.all()) == [earlier]


def test_complete_change_queues_email_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    password_changed_email_delay: Mock,
    consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        PasswordChangeService().complete_change(consumer_user)

    assert len(callbacks) == 1
    password_changed_email_delay.assert_not_called()


def test_complete_change_queues_email_for_user(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    password_changed_email_delay: Mock,
    consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        PasswordChangeService().complete_change(consumer_user)

    password_changed_email_delay.assert_called_once_with(consumer_user.pk)


@pytest.mark.usefixtures("password_changed_email_delay")
def test_complete_change_logs_changed(json_logs: io.StringIO, consumer_user: User) -> None:
    PasswordChangeService().complete_change(consumer_user)

    [line] = events(json_logs, "password_changed")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)


def test_complete_change_logs_when_email_cannot_be_queued(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    password_changed_email_delay: Mock,
    consumer_user: User,
) -> None:
    password_changed_email_delay.side_effect = OperationalError("broker unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        PasswordChangeService().complete_change(consumer_user)

    [line] = events(json_logs, "password_changed_email_queue_failed")
    assert (line["level"], line["user_id"]) == ("error", consumer_user.pk)
