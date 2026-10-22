import io
from unittest.mock import Mock

import pytest
from kombu.exceptions import OperationalError
from pytest_django import DjangoCaptureOnCommitCallbacks

from tests.logging_support import events
from users.models import ThrottleEvent, User
from users.services.invite_service import InviteService
from users.services.login_failure_service import LoginFailureService


@pytest.fixture
def invite_email_delay(monkeypatch: pytest.MonkeyPatch) -> Mock:
    delay = Mock()
    monkeypatch.setattr("users.services.invite_service.send_invite_email.delay", delay)
    return delay


@pytest.mark.django_db
@pytest.mark.usefixtures("invite_email_delay")
def test_invite_creates_user_without_password() -> None:
    user = InviteService().invite(email=" Invited@Example.com ")

    user.refresh_from_db()
    assert user.email == "invited@example.com"
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_invite_queues_email_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks, invite_email_delay: Mock
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        InviteService().invite(email="invited@example.com")

    assert len(callbacks) == 1
    invite_email_delay.assert_not_called()


@pytest.mark.django_db
def test_invite_queues_email_for_new_user(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks, invite_email_delay: Mock
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        user = InviteService().invite(email="invited@example.com")

    invite_email_delay.assert_called_once_with(user.pk)


@pytest.mark.django_db
@pytest.mark.usefixtures("invite_email_delay")
def test_invite_logs_user_invited(json_logs: io.StringIO) -> None:
    user = InviteService().invite(email="invited@example.com")

    [line] = events(json_logs, "user_invited")
    assert (line["level"], line["user_id"]) == ("info", user.pk)


def test_resend_queues_email_for_user(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    invite_email_delay: Mock,
    invited_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        InviteService().resend(invited_user.pk)

    invite_email_delay.assert_called_once_with(invited_user.pk)


def test_resend_logs_requested(
    json_logs: io.StringIO, invite_email_delay: Mock, invited_user: User
) -> None:
    InviteService().resend(invited_user.pk)

    [line] = events(json_logs, "invite_resend_requested")
    assert (line["level"], line["user_id"]) == ("info", invited_user.pk)


def test_invite_logs_when_email_cannot_be_queued(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    invite_email_delay: Mock,
    invited_user: User,
) -> None:
    invite_email_delay.side_effect = OperationalError("broker unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        InviteService().resend(invited_user.pk)

    [line] = events(json_logs, "invite_email_queue_failed")
    assert (line["level"], line["user_id"]) == ("error", invited_user.pk)


def test_accept_verifies_email(invited_user: User) -> None:
    InviteService().accept(invited_user, "198.51.100.1")

    invited_user.refresh_from_db()
    assert invited_user.is_email_verified


def test_accept_clears_own_failures_only(invited_user: User) -> None:
    failures = LoginFailureService()
    failures.record_attempt(invited_user.email, "198.51.100.1")
    failures.record_attempt(invited_user.email, "203.0.113.7")

    InviteService().accept(invited_user, "198.51.100.1")

    assert list(ThrottleEvent.objects.values_list("ip", flat=True)) == ["203.0.113.7"]


def test_accept_logs_invite_accepted(json_logs: io.StringIO, invited_user: User) -> None:
    InviteService().accept(invited_user, None)

    [line] = events(json_logs, "invite_accepted")
    assert (line["level"], line["user_id"]) == ("info", invited_user.pk)
