from typing import Any

from celery import shared_task
from django.db import InterfaceError, OperationalError

from audit.services.audit_event_service import AuditEventService


# Takes the masked row, not ids: the request it describes is gone.
@shared_task(
    autoretry_for=(OperationalError, InterfaceError),
    retry_backoff=True,
    max_retries=3,
    time_limit=30,
    acks_late=False,
)
def record_incoming_event(event: dict[str, Any]) -> None:
    AuditEventService().create_incoming_event(event)
