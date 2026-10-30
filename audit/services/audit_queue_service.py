from time import monotonic
from typing import Any

import structlog
from kombu.exceptions import OperationalError

from audit.tasks import record_incoming_event

logger = structlog.get_logger(__name__)


class AuditQueueService:
    publish_pause_seconds = 10

    # The middleware keeps one instance per process, so the pause is shared by its requests.
    def __init__(self) -> None:
        self._paused_until = 0.0

    # A blocked broker makes each publish wait ~4 s: after a failure, drop rows for a while instead.
    def queue_incoming_event(self, event: dict[str, Any]) -> None:
        if monotonic() < self._paused_until:
            return
        try:
            record_incoming_event.delay(event)
        except OperationalError:
            self._paused_until = monotonic() + self.publish_pause_seconds
            logger.exception("audit_event_queue_failed", event_type=event["type"])
