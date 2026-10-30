import json
from datetime import datetime, timedelta
from typing import Any

import pytest
from django.http import JsonResponse
from django.test import RequestFactory
from django.utils import timezone
from pytest_django import Settings

from audit.enums import EventType
from audit.incoming_event_builder import IncomingEventBuilder
from audit.models import IncomingRequestResponseEvent
from audit.services.audit_event_service import AuditEventService
from audit.signals import remember_request_error


def through_broker(event: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = json.loads(json.dumps(event))
    return result


@pytest.mark.django_db(databases=["log"])
def test_create_incoming_event_saves_request_event(rf: RequestFactory) -> None:
    event = IncomingEventBuilder().build_request_event(rf.post("/?page=2", {"name": "x"}))

    AuditEventService().create_incoming_event(through_broker(event))

    row = IncomingRequestResponseEvent.objects.get()
    assert row.type == EventType.REQUEST
    assert row.path == "/"
    assert row.data["params"] == {"page": ["2"]}
    assert row.logged_at == datetime.fromisoformat(event["logged_at"])


@pytest.mark.django_db(databases=["log"])
def test_create_incoming_event_saves_response_event_with_error(rf: RequestFactory) -> None:
    request = rf.get("/")
    try:
        raise ValueError
    except ValueError:
        remember_request_error(sender=None, request=request)
    event = IncomingEventBuilder().build_response_event(
        request, JsonResponse({"ok": False}), duration_ms=5
    )

    AuditEventService().create_incoming_event(through_broker(event))

    row = IncomingRequestResponseEvent.objects.get()
    assert row.type == EventType.RESPONSE
    assert row.status == event["status"]
    assert row.duration_ms == 5
    assert row.error is not None
    assert row.error["error_type"] == "ValueError"


def create_event_logged_days_ago(days: float) -> IncomingRequestResponseEvent:
    return IncomingRequestResponseEvent.objects.create(
        type=EventType.REQUEST,
        request_id="req-1",
        method="GET",
        path="/",
        logged_at=timezone.now() - timedelta(days=days),
    )


@pytest.mark.django_db(databases=["log"])
def test_delete_expired_keeps_events_within_retention(settings: Settings) -> None:
    settings.AUDIT_RETENTION_DAYS = 90
    create_event_logged_days_ago(90.01)
    kept = create_event_logged_days_ago(89.99)

    deleted = AuditEventService().delete_expired()

    assert deleted == 1
    assert list(IncomingRequestResponseEvent.objects.all()) == [kept]


@pytest.mark.django_db(databases=["log"])
def test_delete_expired_deletes_in_batches(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> None:
    settings.AUDIT_RETENTION_DAYS = 1
    monkeypatch.setattr(AuditEventService, "delete_batch_size", 2)
    for _ in range(5):
        create_event_logged_days_ago(2)

    deleted = AuditEventService().delete_expired()

    assert deleted == 5
    assert not IncomingRequestResponseEvent.objects.exists()
