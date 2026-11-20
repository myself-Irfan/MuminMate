from typing import Any
from unittest.mock import Mock

import pytest
from celery import Task
from celery.exceptions import Retry
from django.db import InterfaceError, OperationalError
from django.test import RequestFactory
from django.utils import timezone

from audit.enums import EventType, Partner
from audit.incoming_event_builder import IncomingEventBuilder
from audit.models import IncomingRequestResponseEvent, OutgoingRequestResponseEvent
from audit.tasks import record_incoming_event, record_outgoing_event

type AuditTask = Task[[dict[str, Any]], None]
type AuditTaskCase = tuple[AuditTask, str]


@pytest.fixture(
    params=[
        (record_incoming_event, "audit.tasks.AuditEventService.create_incoming_event"),
        (record_outgoing_event, "audit.tasks.AuditEventService.create_outgoing_event"),
    ],
    ids=["incoming", "outgoing"],
)
def audit_task(request: pytest.FixtureRequest) -> AuditTaskCase:
    task_and_service_method: AuditTaskCase = request.param
    return task_and_service_method


@pytest.mark.django_db(databases=["log"])
def test_record_incoming_event_saves_event(rf: RequestFactory) -> None:
    event = IncomingEventBuilder().build_request_event(rf.get("/"))

    record_incoming_event(event)

    assert IncomingRequestResponseEvent.objects.get().path == "/"


@pytest.mark.django_db(databases=["log"])
def test_record_outgoing_event_saves_event() -> None:
    event = {
        "type": EventType.REQUEST,
        "request_id": "req-1",
        "partner": Partner.EMAIL,
        "name": "password_reset",
        "method": "SMTP",
        "url": "smtp://mailpit:1025",
        "logged_at": timezone.now().isoformat(),
    }

    record_outgoing_event(event)

    assert OutgoingRequestResponseEvent.objects.get().name == "password_reset"


@pytest.mark.parametrize("error", [OperationalError(), InterfaceError()])
def test_record_event_retries_when_database_unreachable(
    monkeypatch: pytest.MonkeyPatch, audit_task: AuditTaskCase, error: Exception
) -> None:
    task, service_method = audit_task
    monkeypatch.setattr(service_method, Mock(side_effect=error))
    backoff = Mock(return_value=1)
    monkeypatch.setattr("celery.app.autoretry.get_exponential_backoff_interval", backoff)
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(task, "retry", retry)

    with pytest.raises(Retry):
        task({})

    backoff.assert_called_once_with(factor=1, retries=0, maximum=600, full_jitter=True)
    retry.assert_called_once_with(exc=error, countdown=1)


# A bad row fails the same way every time.
def test_record_event_fails_without_retry_when_event_invalid(
    monkeypatch: pytest.MonkeyPatch, audit_task: AuditTaskCase
) -> None:
    task, _ = audit_task
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(task, "retry", retry)

    with pytest.raises(TypeError):
        task({"unknown_field": 1})

    retry.assert_not_called()


# Tripwire: time limits act only under prefork; an insert takes ms, so this only stops a hung one.
def test_record_event_time_and_retry_limits(audit_task: AuditTaskCase) -> None:
    task, _ = audit_task

    assert (task.time_limit, task.max_retries) == (30, 3)


# At most once: a crash loses the row rather than saving it twice.
def test_record_event_acked_before_running(audit_task: AuditTaskCase) -> None:
    task, _ = audit_task

    assert task.acks_late is False
