import io
from collections.abc import Iterator
from typing import Any

import pytest
import structlog
from django.test import Client, RequestFactory
from django_structlog.celery.receivers import CeleryReceiver
from django_structlog.middlewares import RequestMiddleware

from core.signals import mark_health_probe
from tests.logging_support import json_lines


@pytest.fixture
def clear_contextvars() -> Iterator[None]:
    yield
    structlog.contextvars.clear_contextvars()


def test_request_events_log_remote_addr_not_forwarded_for(
    client: Client, json_logs: io.StringIO
) -> None:
    client.get("/api/nope", headers={"X-Forwarded-For": "198.51.100.9"}, REMOTE_ADDR="203.0.113.7")

    assert {line["ip"] for line in json_lines(json_logs)} == {"203.0.113.7"}


@pytest.mark.usefixtures("clear_contextvars")
@pytest.mark.parametrize("path", ["/api/health/live", "/api/health/ready"])
def test_health_probe_marked(rf: RequestFactory, path: str) -> None:
    mark_health_probe(sender=RequestMiddleware, request=rf.get(path))

    assert structlog.contextvars.get_contextvars() == {"is_probe": True}


@pytest.mark.usefixtures("clear_contextvars")
@pytest.mark.parametrize("path", ["/accounts/login/", "/api/health/nope", "/api/nope"])
def test_other_requests_not_marked(rf: RequestFactory, path: str) -> None:
    mark_health_probe(sender=RequestMiddleware, request=rf.get(path))

    assert structlog.contextvars.get_contextvars() == {}


@pytest.mark.usefixtures("clear_contextvars")
def test_task_headers_carry_only_ids() -> None:
    structlog.contextvars.bind_contextvars(
        request_id="r1", task_id="t0", user_id=7, ip="203.0.113.9", is_probe=True
    )
    headers: dict[str, Any] = {}

    CeleryReceiver().receiver_before_task_publish(headers=headers, properties={})

    assert headers["__django_structlog__"] == {
        "request_id": "r1",
        "parent_task_id": "t0",
        "user_id": 7,
    }
