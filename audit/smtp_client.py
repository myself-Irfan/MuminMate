from email.utils import make_msgid
from time import monotonic

from django.conf import settings
from django.core.mail import EmailMessage
from django.core.mail.utils import DNS_NAME

from audit.enums import Partner
from audit.outgoing_event_builder import OutgoingCall, OutgoingEventBuilder
from audit.services.audit_queue_service import AuditQueueService
from core.smtp import get_smtp_code


class SmtpClient:
    # One per process, so the pause after a failed publish is shared by every send.
    audit_queue = AuditQueueService()
    builder = OutgoingEventBuilder()
    # smtplib names no reply codes.
    accepted_code = 250

    def send(self, mail: EmailMessage, name: str, recipient_id: int) -> None:
        # Set before sending so the REQUEST row has it; Django keeps an existing one.
        message_id = mail.extra_headers.setdefault("Message-ID", make_msgid(domain=DNS_NAME))
        call = OutgoingCall(
            partner=Partner.EMAIL,
            name=name,
            method="SMTP",
            url=f"smtp://{settings.EMAIL_HOST}:{settings.EMAIL_PORT}",
            additional_info={"recipient_id": recipient_id, "message_id": message_id},
        )
        self.audit_queue.queue_outgoing_event(
            self.builder.build_request_event(call, data={"size": len(mail.message().as_bytes())})
        )
        start = monotonic()
        try:
            mail.send()
        except OSError as error:
            self._queue_response(call, start, get_smtp_code(error), type(error).__name__)
            raise
        # One recipient, so a return means the server accepted it.
        self._queue_response(call, start, self.accepted_code, None)

    def _queue_response(
        self, call: OutgoingCall, start: float, status: int | None, error_type: str | None
    ) -> None:
        self.audit_queue.queue_outgoing_event(
            self.builder.build_response_event(
                call,
                duration_ms=round((monotonic() - start) * 1000),
                status=status,
                error_type=error_type,
            )
        )
