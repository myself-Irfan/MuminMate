import time
from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from celery.contrib.testing.worker import start_worker
from celery.worker import WorkController
from django.core import mail

from config.celery import app
from users.services.user_service import UserService


# No ping check: it needs Celery's test-only celery.ping task; ensure_started() waits instead.
@pytest.fixture
def email_worker() -> Iterator[WorkController]:
    with start_worker(
        app, queues=["default", "email"], perform_ping_check=False, shutdown_timeout=30
    ) as worker:
        yield worker


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("restore_logging", "email_worker")
def test_signup_email_sent_by_worker_after_commit(password: str) -> None:
    UserService().signup(email="new@example.com", password=password)

    deadline = time.monotonic() + 10
    while not mail.outbox and time.monotonic() < deadline:
        time.sleep(0.1)
    [sent] = mail.outbox
    assert sent.to == ["new@example.com"]


@pytest.mark.django_db(transaction=True)
@pytest.mark.usefixtures("restore_logging", "email_worker")
def test_signup_email_retried_through_broker_after_failure(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    send = Mock(side_effect=[ConnectionRefusedError(), None])
    monkeypatch.setattr("users.services.email_service.EmailMultiAlternatives.send", send)
    monkeypatch.setattr(
        "celery.app.autoretry.get_exponential_backoff_interval", Mock(return_value=1)
    )

    UserService().signup(email="new@example.com", password=password)

    deadline = time.monotonic() + 15
    while send.call_count < 2 and time.monotonic() < deadline:
        time.sleep(0.1)
    assert send.call_count == 2
