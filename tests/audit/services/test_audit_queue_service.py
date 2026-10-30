import io
from unittest.mock import Mock

import pytest
from django.db import transaction
from django.test import RequestFactory
from kombu.exceptions import OperationalError

from audit.enums import EventType
from audit.incoming_event_builder import IncomingEventBuilder
from audit.services.audit_queue_service import AuditQueueService
from tests.logging_support import events


# Not on commit: the row describes the request even when its transaction rolls back.
@pytest.mark.django_db
def test_queue_incoming_event_queues_event_at_once(rf: RequestFactory, audit_publish: Mock) -> None:
    event = IncomingEventBuilder().build_request_event(rf.get("/"))

    with transaction.atomic():
        AuditQueueService().queue_incoming_event(event)

        audit_publish.assert_called_once_with(event)


def test_queue_incoming_event_logs_when_event_cannot_be_queued(
    rf: RequestFactory, json_logs: io.StringIO, audit_publish: Mock
) -> None:
    audit_publish.side_effect = OperationalError("broker unreachable")
    event = IncomingEventBuilder().build_request_event(rf.get("/"))

    AuditQueueService().queue_incoming_event(event)

    [line] = events(json_logs, "audit_event_queue_failed")
    assert (line["level"], line["event_type"]) == ("error", EventType.REQUEST)


def test_queue_incoming_event_pauses_after_failure(
    rf: RequestFactory, json_logs: io.StringIO, audit_publish: Mock
) -> None:
    audit_publish.side_effect = OperationalError("broker blocked")
    service = AuditQueueService()
    event = IncomingEventBuilder().build_request_event(rf.get("/"))

    service.queue_incoming_event(event)
    service.queue_incoming_event(event)

    audit_publish.assert_called_once()
    assert len(events(json_logs, "audit_event_queue_failed")) == 1


def test_queue_incoming_event_publishes_again_after_pause(
    monkeypatch: pytest.MonkeyPatch, rf: RequestFactory, audit_publish: Mock
) -> None:
    clock = Mock(return_value=100.0)
    monkeypatch.setattr("audit.services.audit_queue_service.monotonic", clock)
    audit_publish.side_effect = [OperationalError("broker blocked"), None]
    service = AuditQueueService()
    event = IncomingEventBuilder().build_request_event(rf.get("/"))
    service.queue_incoming_event(event)

    clock.return_value = 100.0 + AuditQueueService.publish_pause_seconds
    service.queue_incoming_event(event)

    assert audit_publish.call_count == 2
