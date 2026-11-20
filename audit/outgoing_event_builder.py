from dataclasses import dataclass
from typing import Any

import structlog
from django.utils import timezone

from audit.enums import EventType, Partner


@dataclass(frozen=True)
class OutgoingCall:
    partner: Partner
    name: str
    method: str
    url: str
    additional_info: dict[str, Any]


# Translates one outgoing call into rows; touches no db or broker.
class OutgoingEventBuilder:
    def build_request_event(self, call: OutgoingCall, data: dict[str, Any]) -> dict[str, Any]:
        return {**self._get_call_fields(call, EventType.REQUEST), "data": data}

    def build_response_event(
        self, call: OutgoingCall, duration_ms: int, status: int | None, error_type: str | None
    ) -> dict[str, Any]:
        return {
            **self._get_call_fields(call, EventType.RESPONSE),
            "status": status,
            "duration_ms": duration_ms,
            "error": {"error_type": error_type} if error_type else None,
        }

    # django-structlog carries both into the task from whoever queued it.
    def _get_call_fields(self, call: OutgoingCall, event_type: EventType) -> dict[str, Any]:
        context = structlog.contextvars.get_contextvars()
        return {
            "type": event_type,
            "request_id": context.get("request_id", ""),
            "partner": call.partner,
            "name": call.name,
            "method": call.method,
            "url": call.url,
            "user_id": context.get("user_id"),
            "additional_info": call.additional_info,
            "logged_at": timezone.now().isoformat(),
        }
