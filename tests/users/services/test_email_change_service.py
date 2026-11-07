import io
from unittest.mock import Mock

import pytest
from kombu.exceptions import OperationalError
from pytest_django import DjangoCaptureOnCommitCallbacks

from tests.logging_support import events
from users.enums import ThrottleScope
from users.exceptions import (
    EmailChangeLinkForOtherAccountError,
    EmailTakenError,
    InvalidEmailChangeLinkError,
)
from users.models import ThrottleEvent, User
from users.services.email_change_service import EmailChangeService
from users.tokens import EmailChangeSigner


@pytest.fixture
def invite_resend(monkeypatch: pytest.MonkeyPatch) -> Mock:
    resend = Mock()
    monkeypatch.setattr("users.services.email_change_service.InviteService.resend", resend)
    return resend


@pytest.fixture
def verification_reset(monkeypatch: pytest.MonkeyPatch) -> Mock:
    reset = Mock()
    monkeypatch.setattr(
        "users.services.email_change_service.EmailVerificationService.reset_verification", reset
    )
    return reset


@pytest.fixture
def email_change_token(consumer_user: User) -> str:
    return EmailChangeSigner().make_token(consumer_user, "new@example.com")


# The old invite link dies with the old address; the new one confirms the email too.
@pytest.mark.parametrize("is_staff", [False, True], ids=["consumer", "staff"])
def test_complete_admin_change_resends_invite_when_invite_pending(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    invite_resend: Mock,
    verification_reset: Mock,
    email_changed_notice_delay: Mock,
    invited_user: User,
    is_staff: bool,
) -> None:
    User.objects.filter(pk=invited_user.pk).update(is_staff=is_staff)
    invited_user.refresh_from_db()

    with django_capture_on_commit_callbacks(execute=True):
        EmailChangeService().complete_admin_change(invited_user, "old@example.com")

    invite_resend.assert_called_once_with(invited_user.pk)
    verification_reset.assert_not_called()


@pytest.mark.parametrize("is_staff", [False, True], ids=["consumer", "staff"])
def test_complete_admin_change_sends_no_notice_when_invite_pending(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    invite_resend: Mock,
    email_changed_notice_delay: Mock,
    invited_user: User,
    is_staff: bool,
) -> None:
    User.objects.filter(pk=invited_user.pk).update(is_staff=is_staff)
    invited_user.refresh_from_db()

    with django_capture_on_commit_callbacks(execute=True):
        EmailChangeService().complete_admin_change(invited_user, "old@example.com")

    email_changed_notice_delay.assert_not_called()


def test_complete_admin_change_resets_verification_when_password_set(
    invite_resend: Mock,
    verification_reset: Mock,
    email_changed_notice_delay: Mock,
    consumer_user: User,
) -> None:
    EmailChangeService().complete_admin_change(consumer_user, "old@example.com")

    verification_reset.assert_called_once_with(consumer_user)
    invite_resend.assert_not_called()


# Staff log in at /admin/, which never checks verification; a consumer link would mean nothing.
def test_complete_admin_change_sends_no_link_when_staff_has_password(
    invite_resend: Mock,
    verification_reset: Mock,
    email_changed_notice_delay: Mock,
    staff_user: User,
) -> None:
    EmailChangeService().complete_admin_change(staff_user, "old@example.com")

    invite_resend.assert_not_called()
    verification_reset.assert_not_called()


@pytest.mark.usefixtures("verification_reset")
@pytest.mark.parametrize("user_fixture", ["consumer_user", "staff_user"])
def test_complete_admin_change_queues_notice_to_old_address_only_after_commit(
    request: pytest.FixtureRequest,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    email_changed_notice_delay: Mock,
    user_fixture: str,
) -> None:
    user: User = request.getfixturevalue(user_fixture)

    with django_capture_on_commit_callbacks() as callbacks:
        EmailChangeService().complete_admin_change(user, "old@example.com")
    email_changed_notice_delay.assert_not_called()
    for callback in callbacks:
        callback()

    email_changed_notice_delay.assert_called_once_with(user.pk, "old@example.com")


@pytest.mark.usefixtures("email_changed_notice_delay")
def test_confirm_changes_email_and_marks_it_verified(
    consumer_user: User, email_change_token: str
) -> None:
    EmailChangeService().confirm(consumer_user, email_change_token)

    consumer_user.refresh_from_db()
    assert consumer_user.email == "new@example.com"
    assert consumer_user.is_email_verified


def test_confirm_queues_notice_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    email_changed_notice_delay: Mock,
    consumer_user: User,
    email_change_token: str,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        EmailChangeService().confirm(consumer_user, email_change_token)

    assert len(callbacks) == 1
    email_changed_notice_delay.assert_not_called()


# The row now holds the new address; only the old one can warn a hijacked owner.
def test_confirm_queues_notice_to_old_address(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    email_changed_notice_delay: Mock,
    consumer_user: User,
    email_change_token: str,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        EmailChangeService().confirm(consumer_user, email_change_token)

    email_changed_notice_delay.assert_called_once_with(consumer_user.pk, "irfan@example.com")


@pytest.mark.usefixtures("email_changed_notice_delay")
def test_confirm_logs_changed(
    json_logs: io.StringIO, consumer_user: User, email_change_token: str
) -> None:
    EmailChangeService().confirm(consumer_user, email_change_token)

    [line] = events(json_logs, "email_changed")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)


def test_confirm_keeps_change_when_notice_cannot_be_queued(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    email_changed_notice_delay: Mock,
    consumer_user: User,
    email_change_token: str,
) -> None:
    email_changed_notice_delay.side_effect = OperationalError("broker unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        EmailChangeService().confirm(consumer_user, email_change_token)

    [line] = events(json_logs, "email_changed_notice_queue_failed")
    assert (line["level"], line["user_id"]) == ("error", consumer_user.pk)
    consumer_user.refresh_from_db()
    assert consumer_user.email == "new@example.com"


def test_confirm_raises_when_token_invalid(consumer_user: User) -> None:
    with pytest.raises(InvalidEmailChangeLinkError):
        EmailChangeService().confirm(consumer_user, "not-a-token")

    consumer_user.refresh_from_db()
    assert consumer_user.email == "irfan@example.com"


def test_confirm_raises_when_link_for_other_account(
    consumer_user: User, staff_user: User, email_change_token: str
) -> None:
    with pytest.raises(EmailChangeLinkForOtherAccountError):
        EmailChangeService().confirm(staff_user, email_change_token)

    consumer_user.refresh_from_db()
    staff_user.refresh_from_db()
    assert (consumer_user.email, staff_user.email) == ("irfan@example.com", "staff@example.com")


def test_confirm_raises_when_password_changed_since_sent(
    consumer_user: User, email_change_token: str
) -> None:
    consumer_user.set_password("another-pass-9")
    consumer_user.save()

    with pytest.raises(InvalidEmailChangeLinkError):
        EmailChangeService().confirm(consumer_user, email_change_token)

    consumer_user.refresh_from_db()
    assert consumer_user.email == "irfan@example.com"


# The first of two quick confirms committed after this one loaded the user.
def test_confirm_raises_and_sends_no_notice_when_already_confirmed(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    consumer_user: User,
    email_change_token: str,
) -> None:
    User.objects.filter(pk=consumer_user.pk).update(email="new@example.com")

    with (
        django_capture_on_commit_callbacks() as callbacks,
        pytest.raises(InvalidEmailChangeLinkError),
    ):
        EmailChangeService().confirm(consumer_user, email_change_token)

    assert callbacks == []


def test_confirm_raises_when_email_taken_since_sent(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    consumer_user: User,
    email_change_token: str,
) -> None:
    User.objects.create_user(email="new@example.com", password=None)

    with django_capture_on_commit_callbacks() as callbacks, pytest.raises(EmailTakenError):
        EmailChangeService().confirm(consumer_user, email_change_token)

    assert callbacks == []


def test_get_new_email_returns_address_from_link_without_changing_it(
    consumer_user: User, email_change_token: str
) -> None:
    new_email = EmailChangeService().get_new_email(consumer_user, email_change_token)

    assert new_email == "new@example.com"
    consumer_user.refresh_from_db()
    assert consumer_user.email == "irfan@example.com"


def test_get_new_email_raises_when_token_invalid(consumer_user: User) -> None:
    with pytest.raises(InvalidEmailChangeLinkError):
        EmailChangeService().get_new_email(consumer_user, "not-a-token")


def test_get_new_email_raises_when_link_for_other_account(
    staff_user: User, email_change_token: str
) -> None:
    with pytest.raises(EmailChangeLinkForOtherAccountError):
        EmailChangeService().get_new_email(staff_user, email_change_token)


def test_get_new_email_raises_when_password_changed_since_sent(
    consumer_user: User, email_change_token: str
) -> None:
    consumer_user.set_password("another-pass-9")
    consumer_user.save()

    with pytest.raises(InvalidEmailChangeLinkError):
        EmailChangeService().get_new_email(consumer_user, email_change_token)


@pytest.mark.usefixtures("request_limits")
def test_request_change_queues_link_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    email_change_link_delay: Mock,
    consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        EmailChangeService().request_change(consumer_user, "new@example.com")

    assert len(callbacks) == 1
    email_change_link_delay.assert_not_called()


@pytest.mark.usefixtures("request_limits")
def test_request_change_queues_link_to_new_address(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    email_change_link_delay: Mock,
    consumer_user: User,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        queued = EmailChangeService().request_change(consumer_user, "new@example.com")

    assert queued
    email_change_link_delay.assert_called_once_with(consumer_user.pk, "new@example.com")


@pytest.mark.usefixtures("request_limits", "email_change_link_delay")
def test_request_change_logs_requested(json_logs: io.StringIO, consumer_user: User) -> None:
    EmailChangeService().request_change(consumer_user, "new@example.com")

    [line] = events(json_logs, "email_change_requested")
    assert (line["level"], line["user_id"]) == ("info", consumer_user.pk)


@pytest.mark.usefixtures("request_limits")
def test_request_change_refused_when_limited(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    json_logs: io.StringIO,
    email_change_link_delay: Mock,
    consumer_user: User,
) -> None:
    ThrottleEvent.objects.create(scope=ThrottleScope.EMAIL_CHANGE, user=consumer_user)

    with django_capture_on_commit_callbacks(execute=True):
        queued = EmailChangeService().request_change(consumer_user, "new@example.com")

    assert not queued
    email_change_link_delay.assert_not_called()
    [line] = events(json_logs, "request_limited")
    assert line["scope"] == "email_change"


@pytest.mark.usefixtures("request_limits")
def test_request_change_logs_when_link_cannot_be_queued(
    json_logs: io.StringIO,
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    email_change_link_delay: Mock,
    consumer_user: User,
) -> None:
    email_change_link_delay.side_effect = OperationalError("broker unreachable")

    with django_capture_on_commit_callbacks(execute=True):
        EmailChangeService().request_change(consumer_user, "new@example.com")

    [line] = events(json_logs, "email_change_link_queue_failed")
    assert (line["level"], line["user_id"]) == ("error", consumer_user.pk)


@pytest.mark.usefixtures("request_limits")
def test_record_attempt_saves_current_password_try_for_user(consumer_user: User) -> None:
    attempt = EmailChangeService().record_attempt(consumer_user)

    assert attempt == ThrottleEvent.objects.get(
        scope=ThrottleScope.CURRENT_PASSWORD_FAILURE, user=consumer_user
    )


@pytest.mark.usefixtures("request_limits")
def test_record_attempt_refused_when_limit_reached(consumer_user: User) -> None:
    ThrottleEvent.objects.bulk_create(
        ThrottleEvent(scope=ThrottleScope.CURRENT_PASSWORD_FAILURE, user=consumer_user)
        for _ in range(3)
    )

    assert EmailChangeService().record_attempt(consumer_user) is None


@pytest.mark.usefixtures("request_limits")
def test_clear_attempt_deletes_only_that_attempt(consumer_user: User) -> None:
    changes = EmailChangeService()
    earlier = changes.record_attempt(consumer_user)
    attempt = changes.record_attempt(consumer_user)
    assert earlier is not None
    assert attempt is not None

    changes.clear_attempt(attempt)

    assert list(ThrottleEvent.objects.all()) == [earlier]
