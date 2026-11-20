from django.db import models

from audit.enums import EventType, Partner
from core.models import CreatedAtAbstract


class RequestResponseEvent(CreatedAtAbstract):
    type = models.CharField(max_length=8, choices=EventType)
    request_id = models.CharField(max_length=128)
    method = models.CharField(max_length=16)
    # Masked: {"params", "body"} for HTTP, {"size"} for email; each only when present.
    data = models.JSONField(default=dict)
    headers = models.JSONField(default=dict)
    status = models.PositiveSmallIntegerField(null=True)
    duration_ms = models.PositiveIntegerField(null=True)
    error = models.JSONField(null=True)
    # A plain id: the router refuses foreign keys across databases.
    user_id = models.PositiveBigIntegerField(null=True)
    # Context that needs no column of its own.
    additional_info = models.JSONField(default=dict)
    logged_at = models.DateTimeField()

    class Meta:
        abstract = True


class IncomingRequestResponseEvent(RequestResponseEvent):
    url_name = models.CharField(max_length=128, blank=True)
    path = models.TextField()

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


class OutgoingRequestResponseEvent(RequestResponseEvent):
    partner = models.CharField(max_length=16, choices=Partner)
    # What was called: the email kind or the API operation.
    name = models.CharField(max_length=128)
    url = models.TextField()

    class Meta:
        db_table = "outgoing_request_response_events"
        indexes = (
            models.Index(fields=("request_id",), name="outgoing_events_request_id_idx"),
            models.Index(fields=("logged_at",), name="outgoing_events_logged_at_idx"),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(type__in=EventType.values),
                name="outgoing_request_response_events_type_valid",
                violation_error_message="Unknown event type.",
            ),
            models.CheckConstraint(
                condition=models.Q(partner__in=Partner.values),
                name="outgoing_request_response_events_partner_valid",
                violation_error_message="Unknown partner.",
            ),
        )

    def __str__(self) -> str:
        return f"{self.type} {self.partner} {self.name} ({self.request_id})"
