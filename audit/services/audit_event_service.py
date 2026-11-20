from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from audit.models import (
    IncomingRequestResponseEvent,
    OutgoingRequestResponseEvent,
    RequestResponseEvent,
)


class AuditEventService:
    delete_batch_size = 5000

    def create_incoming_event(self, event: dict[str, Any]) -> None:
        IncomingRequestResponseEvent.objects.create(**event)

    def create_outgoing_event(self, event: dict[str, Any]) -> None:
        OutgoingRequestResponseEvent.objects.create(**event)

    def delete_expired(self) -> int:
        cutoff = timezone.now() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
        return sum(
            self._delete_logged_before(model, cutoff)
            for model in (IncomingRequestResponseEvent, OutgoingRequestResponseEvent)
        )

    # In batches: one DELETE of millions of rows holds its locks and bloats the WAL in one go.
    def _delete_logged_before(self, model: type[RequestResponseEvent], cutoff: datetime) -> int:
        expired = model._default_manager.filter(logged_at__lt=cutoff)
        deleted = 0
        while batch := list(expired.values_list("pk", flat=True)[: self.delete_batch_size]):
            deleted += model._default_manager.filter(pk__in=batch).delete()[0]
        return deleted
