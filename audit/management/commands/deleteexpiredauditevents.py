from typing import Any

from django.core.management.base import BaseCommand

from audit.services.audit_event_service import AuditEventService


class Command(BaseCommand):
    help = "Delete request audit events older than DJANGO_AUDIT_RETENTION_DAYS."

    def handle(self, *args: Any, **options: Any) -> None:
        deleted = AuditEventService().delete_expired()
        self.stdout.write(f"Deleted {deleted} expired audit events.")
