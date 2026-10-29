from smtplib import (
    SMTPAuthenticationError,
    SMTPRecipientsRefused,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)
from unittest.mock import Mock

import pytest
from celery import Task
from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.core import mail

from users.models import User
from users.tasks import (
    send_invite_email,
    send_password_reset_email,
    send_verification_email,
)

type EmailTask = Task[[int], None]
type EmailTaskCase = tuple[EmailTask, str]


@pytest.fixture(
    params=[
        (send_verification_email, "users.tasks.EmailService.send_verification_email"),
        (send_password_reset_email, "users.tasks.EmailService.send_password_reset_email"),
        (send_invite_email, "users.tasks.EmailService.send_invite_email"),
    ],
    ids=["verification", "password_reset", "invite"],
)
def email_task(request: pytest.FixtureRequest) -> EmailTaskCase:
    task_and_service_method: EmailTaskCase = request.param
    return task_and_service_method


@pytest.mark.parametrize(
    ("task", "user_fixture"),
    [
        (send_verification_email, "unverified_consumer_user"),
        (send_password_reset_email, "consumer_user"),
        (send_invite_email, "invited_user"),
    ],
    ids=["verification", "password_reset", "invite"],
)
def test_email_task_sends_mail(
    request: pytest.FixtureRequest, task: EmailTask, user_fixture: str
) -> None:
    user: User = request.getfixturevalue(user_fixture)

    task(user.pk)

    [sent] = mail.outbox
    assert sent.to == [user.email]


@pytest.mark.parametrize(
    "error", [ConnectionRefusedError(), SMTPServerDisconnected(), SoftTimeLimitExceeded()]
)
def test_email_task_retries_when_error_temporary(
    monkeypatch: pytest.MonkeyPatch, email_task: EmailTaskCase, error: Exception
) -> None:
    task, service_method = email_task
    monkeypatch.setattr(service_method, Mock(side_effect=error))
    backoff = Mock(return_value=42)
    monkeypatch.setattr("celery.app.autoretry.get_exponential_backoff_interval", backoff)
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(task, "retry", retry)

    with pytest.raises(Retry):
        task(1)

    backoff.assert_called_once_with(factor=60, retries=0, maximum=600, full_jitter=True)
    retry.assert_called_once_with(exc=error, countdown=42)


@pytest.mark.parametrize(
    "error",
    [
        SMTPRecipientsRefused({"user@example.com": (550, b"No such user")}),
        SMTPSenderRefused(550, b"Sender rejected", "no-reply@example.com"),
        SMTPAuthenticationError(535, b"Bad credentials"),
    ],
)
def test_email_task_fails_without_retry_when_error_permanent(
    monkeypatch: pytest.MonkeyPatch, email_task: EmailTaskCase, error: Exception
) -> None:
    task, service_method = email_task
    monkeypatch.setattr(service_method, Mock(side_effect=error))
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(task, "retry", retry)

    with pytest.raises(type(error)):
        task(1)

    retry.assert_not_called()


# Tripwire: the time limits only act under prefork, so this pins the decided numbers.
def test_email_task_time_and_retry_limits(email_task: EmailTaskCase) -> None:
    task, _ = email_task

    assert (task.soft_time_limit, task.time_limit, task.max_retries) == (30, 60, 5)


def test_email_task_redelivered_when_worker_lost(email_task: EmailTaskCase) -> None:
    task, _ = email_task

    assert (task.acks_late, task.reject_on_worker_lost) == (True, True)
