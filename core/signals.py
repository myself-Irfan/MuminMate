from typing import Any

import structlog
from django.http import HttpRequest
from django.urls import Resolver404, resolve


# django-structlog's own IP comes from ipware, which trusts the client's X-Forwarded-For.
def bind_client_ip(sender: object, request: HttpRequest, **kwargs: Any) -> None:
    structlog.contextvars.bind_contextvars(ip=request.META.get("REMOTE_ADDR"))


# Read by drop_successful_probes.
def mark_health_probe(sender: object, request: HttpRequest, **kwargs: Any) -> None:
    try:
        view_name = resolve(request.path_info).view_name
    except Resolver404:
        return
    if view_name in {"api:health-live", "api:health-ready"}:
        structlog.contextvars.bind_contextvars(is_probe=True)


# Edited in place: django-structlog sends this dict as the task's headers.
def trim_task_context(sender: object, context: dict[str, Any], **kwargs: Any) -> None:
    kept: dict[str, Any] = {
        key: context[key] for key in ("request_id", "parent_task_id", "user_id") if key in context
    }
    context.clear()
    context.update(kept)
