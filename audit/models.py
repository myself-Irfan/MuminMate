from django.db import models
from django.db.models.functions import Now

from audit.enums import EventType


class IncomingRequestResponseEvent(models.Model):
    max_method_length = 16

    type = models.CharField(max_length=8, choices=EventType)
    request_id = models.CharField(max_length=128)
    url_name = models.CharField(max_length=128, blank=True)
    method = models.CharField(max_length=max_method_length)
    path = models.TextField()
    # {"params": ..., "body": ...}, each only when present (tk-backend's layout).
    data = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    status = models.PositiveSmallIntegerField(null=True)
    duration_ms = models.PositiveIntegerField(null=True)
    error = models.JSONField(null=True)
    # A plain id: the router refuses foreign keys across databases.
    user_id = models.PositiveBigIntegerField(null=True)
    # Request context that needs no column of its own: {"ip": ...} for now.
    additional_info = models.JSONField(default=dict)
    logged_at = models.DateTimeField()
    created_at = models.DateTimeField(db_default=Now())

    class Meta:
        db_table = "incoming_request_response_events"
        indexes = (
            models.Index(fields=("request_id",), name="incoming_events_request_id_idx"),
            models.Index(fields=("logged_at",), name="incoming_events_logged_at_idx"),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(type__in=EventType.values),
                name="incoming_request_response_events_type_valid",
                violation_error_message="Unknown event type.",
            ),
        )

    def __str__(self) -> str:
        return f"{self.type} {self.method} {self.path} ({self.request_id})"
