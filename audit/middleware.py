from collections.abc import Callable
from http import HTTPStatus
from time import perf_counter
from typing import Any

import structlog
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest
from django.http.response import HttpResponseBase

from audit.incoming_event_builder import IncomingEventBuilder
from audit.services.audit_queue_service import AuditQueueService


# After django-structlog's middleware (reads its is_probe), before Security (sees its rejections).
class AuditMiddleware:
    skippable_methods = frozenset({"GET", "HEAD"})
    skippable_statuses = frozenset({HTTPStatus.OK, HTTPStatus.NOT_MODIFIED})

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponseBase]) -> None:
        self.get_response = get_response
        self.builder = IncomingEventBuilder()
        self.service = AuditQueueService()
        if settings.STATIC_URL is None:
            raise ImproperlyConfigured("AuditMiddleware needs STATIC_URL to spot static files.")
        self.static_url = settings.STATIC_URL

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        start = perf_counter()
        request_event = self.builder.build_request_event(request)
        # Held back: only the response shows whether it was a clean hit.
        may_skip = self._is_clean_probe_or_static_request(request, request_event)
        if not may_skip:
            self.service.queue_incoming_event(request_event)

        response = self.get_response(request)

        if may_skip:
            if response.status_code in self.skippable_statuses:
                return response
            self.service.queue_incoming_event(request_event)
        duration_ms = round((perf_counter() - start) * 1000)
        self.service.queue_incoming_event(
            self.builder.build_response_event(request, response, duration_ms)
        )
        return response

    def _is_clean_probe_or_static_request(
        self, request: HttpRequest, request_event: dict[str, Any]
    ) -> bool:
        is_probe = structlog.contextvars.get_contextvars().get("is_probe") is True
        is_static = request.path.startswith(self.static_url)
        return (
            (is_probe or is_static)
            and request.method in self.skippable_methods
            and not request.META.get("QUERY_STRING")
            and "body" not in request_event["data"]
        )
