from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.test import Client, RequestFactory
from pytest_django import Settings

from audit.enums import EventType
from audit.middleware import AuditMiddleware
from users.models import User


@pytest.fixture
def queued(monkeypatch: pytest.MonkeyPatch) -> Mock:
    queue = Mock()
    monkeypatch.setattr("audit.middleware.AuditQueueService.queue_incoming_event", queue)
    return queue


def queued_types(queue: Mock) -> list[str]:
    return [call.args[0]["type"] for call in queue.call_args_list]


def test_middleware_queues_request_before_view_and_response_after(
    monkeypatch: pytest.MonkeyPatch, rf: RequestFactory
) -> None:
    order = Mock()
    order.get_response.return_value = HttpResponse()
    monkeypatch.setattr("audit.middleware.AuditQueueService.queue_incoming_event", order.queue)

    AuditMiddleware(order.get_response)(rf.get("/accounts/login/"))

    assert [name for name, _, _ in order.mock_calls] == ["queue", "get_response", "queue"]
    assert queued_types(order.queue) == [EventType.REQUEST, EventType.RESPONSE]


def test_middleware_records_duration(
    monkeypatch: pytest.MonkeyPatch, rf: RequestFactory, queued: Mock
) -> None:
    monkeypatch.setattr("audit.middleware.perf_counter", Mock(side_effect=[1.0, 1.25]))

    AuditMiddleware(Mock(return_value=HttpResponse()))(rf.get("/"))

    assert queued.call_args.args[0]["duration_ms"] == 250


def test_middleware_records_page_through_full_stack(client: Client, queued: Mock) -> None:
    response = client.get("/accounts/login/")

    request_event, response_event = (call.args[0] for call in queued.call_args_list)
    assert request_event["request_id"] == response_event["request_id"] == response["X-Request-ID"]
    assert response_event["status"] == HTTPStatus.OK


@pytest.mark.django_db
def test_middleware_records_logged_in_user(
    client: Client, consumer_user: User, queued: Mock
) -> None:
    client.force_login(consumer_user)

    client.get("/")

    assert queued.call_args.args[0]["user_id"] == consumer_user.pk


def test_middleware_skips_successful_probe(client: Client, queued: Mock) -> None:
    client.get("/api/health/live")

    queued.assert_not_called()


# Only a clean probe is noise: anything else may be someone hiding behind the probe's path.
@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/api/health/live?x=1"), ("post", "/api/health/live")],
    ids=["query", "post"],
)
def test_middleware_records_probe_unless_clean(
    client: Client, queued: Mock, method: str, path: str
) -> None:
    getattr(client, method)(path)

    assert queued_types(queued) == [EventType.REQUEST, EventType.RESPONSE]


def test_middleware_records_failing_probe(
    monkeypatch: pytest.MonkeyPatch, client: Client, queued: Mock
) -> None:
    monkeypatch.setattr("core.api.HealthService.is_db_ready", Mock(return_value=False))

    client.get("/api/health/ready")

    assert queued_types(queued) == [EventType.REQUEST, EventType.RESPONSE]


@pytest.mark.parametrize("status", [HTTPStatus.OK, HTTPStatus.NOT_MODIFIED])
def test_middleware_skips_served_static_file(
    rf: RequestFactory, queued: Mock, status: HTTPStatus
) -> None:
    AuditMiddleware(Mock(return_value=HttpResponse(status=status)))(
        rf.get(f"{settings.STATIC_URL}css/theme.css")
    )

    queued.assert_not_called()


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("css/missing.css", HTTPStatus.NOT_FOUND),
        ("css/theme.css?x=1", HTTPStatus.OK),
    ],
    ids=["missing", "query"],
)
def test_middleware_records_static_request_unless_clean_hit(
    rf: RequestFactory, queued: Mock, path: str, status: HTTPStatus
) -> None:
    AuditMiddleware(Mock(return_value=HttpResponse(status=status)))(
        rf.get(f"{settings.STATIC_URL}{path}")
    )

    assert queued_types(queued) == [EventType.REQUEST, EventType.RESPONSE]


def test_middleware_records_static_upload_attempt(rf: RequestFactory, queued: Mock) -> None:
    request = rf.post(f"{settings.STATIC_URL}css/theme.css", {"x": "1"})

    AuditMiddleware(Mock(return_value=HttpResponse()))(request)

    assert queued_types(queued) == [EventType.REQUEST, EventType.RESPONSE]


def test_middleware_installed_after_structlog_and_before_security() -> None:
    middleware = settings.MIDDLEWARE

    position = middleware.index("audit.middleware.AuditMiddleware")
    assert middleware[position - 1] == "django_structlog.middlewares.RequestMiddleware"
    assert middleware[position + 1] == "django.middleware.security.SecurityMiddleware"


def test_middleware_records_static_get_with_body(rf: RequestFactory, queued: Mock) -> None:
    request = rf.generic("GET", f"{settings.STATIC_URL}css/theme.css", b"x", "text/plain")

    AuditMiddleware(Mock(return_value=HttpResponse()))(request)

    assert queued_types(queued) == [EventType.REQUEST, EventType.RESPONSE]


def test_middleware_refuses_to_start_without_static_url(settings: Settings) -> None:
    settings.STATIC_URL = None

    with pytest.raises(ImproperlyConfigured, match="STATIC_URL"):
        AuditMiddleware(Mock())


def test_middleware_answers_normally_when_body_breaks_json_parser(
    client: Client, queued: Mock
) -> None:
    response = client.post("/api/health/live", "1" * 5_000, content_type="application/json")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


def test_middleware_answers_normally_when_referer_is_unparseable(
    client: Client, queued: Mock
) -> None:
    response = client.get("/api/health/live", headers={"Referer": "http://["})

    assert response.status_code == HTTPStatus.OK
