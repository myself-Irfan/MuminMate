from smtplib import SMTPServerDisconnected
from unittest.mock import Mock

import pytest
from celery import Task
from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.core import mail

from users.models import User
from users.tasks import (
    send_email_change_link,
    send_email_changed_notice,
    send_invite_email,
    send_password_changed_email,
    send_password_reset_email,
    send_verification_email,
)

type EmailTask = Task[..., None]
type EmailTaskCase = tuple[EmailTask, str, tuple[object, ...]]


@pytest.fixture(
    params=[
        (send_verification_email, "users.tasks.EmailService.send_verification_email", (1,)),
        (send_password_reset_email, "users.tasks.EmailService.send_password_reset_email", (1,)),
        (send_invite_email, "users.tasks.EmailService.send_invite_email", (1,)),
        (
            send_password_changed_email,
            "users.tasks.EmailService.send_password_changed_email",
            (1,),
        ),
        (
            send_email_changed_notice,
            "users.tasks.EmailService.send_email_changed_notice",
            (1, "a@example.com"),
        ),
        (
            send_email_change_link,
            "users.tasks.EmailService.send_email_change_link",
            (1, "new@example.com"),
        ),
    ],
    ids=[
        "verification",
        "password_reset",
        "invite",
        "password_changed",
        "email_changed",
        "email_change_link",
    ],
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
        (send_password_changed_email, "consumer_user"),
    ],
    ids=["verification", "password_reset", "invite", "password_changed"],
)
def test_email_task_sends_mail(
    request: pytest.FixtureRequest, task: EmailTask, user_fixture: str
) -> None:
    user: User = request.getfixturevalue(user_fixture)

    task(user.pk)

    [sent] = mail.outbox
    assert sent.to == [user.email]


def test_email_changed_notice_task_sends_to_old_address(consumer_user: User) -> None:
    send_email_changed_notice(consumer_user.pk, "old@example.com")

    [sent] = mail.outbox
    assert sent.to == ["old@example.com"]


def test_email_change_link_task_sends_to_new_address(consumer_user: User) -> None:
    send_email_change_link(consumer_user.pk, "new@example.com")

    [sent] = mail.outbox
    assert sent.to == ["new@example.com"]


@pytest.mark.parametrize(
    "error", [ConnectionRefusedError(), SMTPServerDisconnected(), SoftTimeLimitExceeded()]
)
def test_email_task_retries_when_error_temporary(
    monkeypatch: pytest.MonkeyPatch, email_task: EmailTaskCase, error: Exception
) -> None:
    task, service_method, args = email_task
    monkeypatch.setattr(service_method, Mock(side_effect=error))
    backoff = Mock(return_value=42)
    monkeypatch.setattr("celery.app.autoretry.get_exponential_backoff_interval", backoff)
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(task, "retry", retry)

    with pytest.raises(Retry):
        task(*args)

    backoff.assert_called_once_with(factor=60, retries=0, maximum=600, full_jitter=True)
    retry.assert_called_once_with(exc=error, countdown=42)


# Tripwire: the time limits only act under prefork, so this pins the decided numbers.
def test_email_task_time_and_retry_limits(email_task: EmailTaskCase) -> None:
    task, _, _ = email_task

    assert (task.soft_time_limit, task.time_limit, task.max_retries) == (30, 60, 5)


def test_email_task_redelivered_when_worker_lost(email_task: EmailTaskCase) -> None:
    task, _, _ = email_task

    assert (task.acks_late, task.reject_on_worker_lost) == (True, True)
