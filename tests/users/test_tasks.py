from smtplib import (
    SMTPAuthenticationError,
    SMTPRecipientsRefused,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)
from unittest.mock import Mock

import pytest
from celery.exceptions import Retry, SoftTimeLimitExceeded
from django.core import mail

from users.models import User
from users.tasks import send_signup_email


def test_signup_email_task_sends_mail(consumer_user: User) -> None:
    send_signup_email(consumer_user.pk)

    [sent] = mail.outbox
    assert sent.to == [consumer_user.email]


@pytest.mark.parametrize(
    "error", [ConnectionRefusedError(), SMTPServerDisconnected(), SoftTimeLimitExceeded()]
)
def test_signup_email_task_retries_when_error_temporary(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setattr(
        "users.tasks.EmailVerificationService.send_signup_email", Mock(side_effect=error)
    )
    backoff = Mock(return_value=42)
    monkeypatch.setattr("celery.app.autoretry.get_exponential_backoff_interval", backoff)
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(send_signup_email, "retry", retry)

    with pytest.raises(Retry):
        send_signup_email(1)

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
def test_signup_email_task_fails_without_retry_when_error_permanent(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setattr(
        "users.tasks.EmailVerificationService.send_signup_email", Mock(side_effect=error)
    )
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(send_signup_email, "retry", retry)

    with pytest.raises(type(error)):
        send_signup_email(1)

    retry.assert_not_called()


# Tripwire: the time limits only act under prefork, so this pins the decided numbers.
def test_signup_email_task_time_and_retry_limits() -> None:
    assert (
        send_signup_email.soft_time_limit,
        send_signup_email.time_limit,
        send_signup_email.max_retries,
    ) == (30, 60, 5)
