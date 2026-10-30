from datetime import timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from audit.models import IncomingRequestResponseEvent


class AuditEventService:
    delete_batch_size = 5000

    def create_incoming_event(self, event: dict[str, Any]) -> None:
        IncomingRequestResponseEvent.objects.create(**event)

    # In batches: one DELETE of millions of rows holds its locks and bloats the WAL in one go.
    def delete_expired(self) -> int:
        cutoff = timezone.now() - timedelta(days=settings.AUDIT_RETENTION_DAYS)
        expired = IncomingRequestResponseEvent.objects.filter(logged_at__lt=cutoff)
        deleted = 0
        while batch := list(expired.values_list("pk", flat=True)[: self.delete_batch_size]):
            deleted += IncomingRequestResponseEvent.objects.filter(pk__in=batch).delete()[0]
        return deleted
