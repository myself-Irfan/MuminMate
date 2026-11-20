from datetime import datetime

import pytest
import structlog
from django.utils import timezone

from audit.enums import EventType, Partner
from audit.outgoing_event_builder import OutgoingCall, OutgoingEventBuilder


@pytest.fixture
def call() -> OutgoingCall:
    return OutgoingCall(
        partner=Partner.EMAIL,
        name="password_reset",
        method="SMTP",
        url="smtp://mailpit:1025",
        additional_info={"recipient_id": 42, "message_id": "<1@muminmate>"},
    )


def test_request_event_records_the_call(call: OutgoingCall) -> None:
    with structlog.contextvars.bound_contextvars(request_id="req-1", user_id=7):
        event = OutgoingEventBuilder().build_request_event(call, data={"size": 6120})

    assert {key: value for key, value in event.items() if key != "logged_at"} == {
        "type": EventType.REQUEST,
        "request_id": "req-1",
        "partner": Partner.EMAIL,
        "name": "password_reset",
        "method": "SMTP",
        "url": "smtp://mailpit:1025",
        "data": {"size": 6120},
        "user_id": 7,
        "additional_info": {"recipient_id": 42, "message_id": "<1@muminmate>"},
    }
    assert datetime.fromisoformat(event["logged_at"]) <= timezone.now()


def test_response_event_records_status_and_duration(call: OutgoingCall) -> None:
    with structlog.contextvars.bound_contextvars(request_id="req-1", user_id=7):
        event = OutgoingEventBuilder().build_response_event(
            call, duration_ms=84, status=250, error_type=None
        )

    assert {key: value for key, value in event.items() if key != "logged_at"} == {
        "type": EventType.RESPONSE,
        "request_id": "req-1",
        "partner": Partner.EMAIL,
        "name": "password_reset",
        "method": "SMTP",
        "url": "smtp://mailpit:1025",
        "status": 250,
        "duration_ms": 84,
        "error": None,
        "user_id": 7,
        "additional_info": {"recipient_id": 42, "message_id": "<1@muminmate>"},
    }
    assert datetime.fromisoformat(event["logged_at"]) <= timezone.now()


def test_response_event_records_error_type_only(call: OutgoingCall) -> None:
    event = OutgoingEventBuilder().build_response_event(
        call, duration_ms=12, status=None, error_type="SMTPAuthenticationError"
    )

    assert (event["status"], event["error"]) == (None, {"error_type": "SMTPAuthenticationError"})


def test_event_without_context_has_empty_request_id_and_no_user(call: OutgoingCall) -> None:
    structlog.contextvars.clear_contextvars()

    event = OutgoingEventBuilder().build_request_event(call, data={})

    assert (event["request_id"], event["user_id"]) == ("", None)
