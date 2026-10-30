from unittest.mock import Mock

import pytest
from celery.exceptions import Retry
from django.db import InterfaceError, OperationalError
from django.test import RequestFactory

from audit.incoming_event_builder import IncomingEventBuilder
from audit.models import IncomingRequestResponseEvent
from audit.tasks import record_incoming_event


@pytest.mark.django_db(databases=["log"])
def test_record_incoming_event_saves_event(rf: RequestFactory) -> None:
    event = IncomingEventBuilder().build_request_event(rf.get("/"))

    record_incoming_event(event)

    assert IncomingRequestResponseEvent.objects.get().path == "/"


@pytest.mark.parametrize("error", [OperationalError(), InterfaceError()])
def test_record_incoming_event_retries_when_database_unreachable(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setattr(
        "audit.tasks.AuditEventService.create_incoming_event", Mock(side_effect=error)
    )
    backoff = Mock(return_value=1)
    monkeypatch.setattr("celery.app.autoretry.get_exponential_backoff_interval", backoff)
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(record_incoming_event, "retry", retry)

    with pytest.raises(Retry):
        record_incoming_event({})

    backoff.assert_called_once_with(factor=1, retries=0, maximum=600, full_jitter=True)
    retry.assert_called_once_with(exc=error, countdown=1)


# A bad row fails the same way every time.
def test_record_incoming_event_fails_without_retry_when_event_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retry = Mock(side_effect=Retry())
    monkeypatch.setattr(record_incoming_event, "retry", retry)

    with pytest.raises(TypeError):
        record_incoming_event({"unknown_field": 1})

    retry.assert_not_called()


# Tripwire: time limits act only under prefork; an insert takes ms, so this only stops a hung one.
def test_record_incoming_event_time_and_retry_limits() -> None:
    assert (record_incoming_event.time_limit, record_incoming_event.max_retries) == (30, 3)


# At most once: a crash loses the row rather than saving it twice.
def test_record_incoming_event_acked_before_running() -> None:
    assert record_incoming_event.acks_late is False
