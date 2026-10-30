import json
from datetime import datetime
from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse, StreamingHttpResponse
from django.test import RequestFactory
from django.utils import timezone
from pytest_django import Settings

from audit.enums import EventType
from audit.incoming_event_builder import IncomingEventBuilder
from audit.models import IncomingRequestResponseEvent
from audit.signals import remember_logged_out_user, remember_request_error
from core.masking import DataMasker
from users.views.authentication_views import ConsumerLoginView
from users.views.password_reset_views import ConsumerPasswordResetConfirmView


@pytest.fixture
def masked() -> str:
    return DataMasker.replacement


def test_request_event_records_the_request(rf: RequestFactory) -> None:
    request = rf.get("/accounts/login/", headers={"X-Request-ID": "req-1"})

    event = IncomingEventBuilder().build_request_event(request)

    assert {key: value for key, value in event.items() if key not in {"headers", "logged_at"}} == {
        "type": EventType.REQUEST,
        "request_id": "req-1",
        "url_name": ConsumerLoginView.url_name,
        "method": "GET",
        "path": "/accounts/login/",
        "data": {},
        "additional_info": {"ip": "127.0.0.1"},
    }
    assert datetime.fromisoformat(event["logged_at"]) <= timezone.now()


def test_request_event_masks_url_token(rf: RequestFactory, masked: str) -> None:
    request = rf.get("/accounts/password-reset/MQ/set-token/")

    event = IncomingEventBuilder().build_request_event(request)

    assert event["path"] == f"/accounts/password-reset/MQ/{masked}/"
    assert event["url_name"] == ConsumerPasswordResetConfirmView.url_name


def test_request_event_url_name_empty_when_no_route_matches(rf: RequestFactory) -> None:
    request = rf.get("/no-such-page/")

    event = IncomingEventBuilder().build_request_event(request)

    assert event["url_name"] == ""
    assert event["path"] == "/no-such-page/"


def test_request_event_method_cut_to_column_length(rf: RequestFactory) -> None:
    request = rf.generic("A" * 40, "/")

    event = IncomingEventBuilder().build_request_event(request)

    assert event["method"] == "A" * IncomingRequestResponseEvent.max_method_length


def test_request_event_masks_query(rf: RequestFactory, masked: str) -> None:
    request = rf.get("/", {"token": "secret", "page": ["1", "2"]})

    event = IncomingEventBuilder().build_request_event(request)

    assert event["data"]["params"] == {"token": [masked], "page": ["1", "2"]}


def test_request_event_masks_headers(rf: RequestFactory, masked: str) -> None:
    request = rf.get("/", headers={"Authorization": "Bearer abc", "User-Agent": "probe"})

    event = IncomingEventBuilder().build_request_event(request)

    assert event["headers"]["Authorization"] == masked
    assert event["headers"]["User-Agent"] == "probe"


def test_request_event_masks_json_body(rf: RequestFactory, masked: str) -> None:
    request = rf.post(
        "/", json.dumps({"email": "a@example.com", "password": "x"}), "application/json"
    )

    event = IncomingEventBuilder().build_request_event(request)

    assert event["data"]["body"] == {"email": "a@example.com", "password": masked}


def test_request_event_masks_form_body(rf: RequestFactory, masked: str) -> None:
    request = rf.post("/", "email=a%40example.com&password=x", "application/x-www-form-urlencoded")

    event = IncomingEventBuilder().build_request_event(request)

    assert event["data"]["body"] == {"email": ["a@example.com"], "password": [masked]}


# A broken login body would otherwise store the password as sent.
@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        ('{"email": "a@example.com", "password": "hunter2"', "application/json"),
        ("hunter2", "text/plain"),
    ],
    ids=["malformed_json", "plain_text"],
)
def test_request_event_stores_only_type_and_size_of_unparsed_text(
    rf: RequestFactory, data: str, content_type: str
) -> None:
    request = rf.post("/", data, content_type)

    event = IncomingEventBuilder().build_request_event(request)

    assert event["data"]["body"] == {"content_type": content_type, "size": len(data)}


@pytest.mark.parametrize(
    ("data", "content_type"),
    [
        (b"\xff\xfe\x00", "application/octet-stream"),
        (
            b"--b\r\nContent-Disposition: form-data; name=f\r\n\r\nx\r\n--b--",
            "multipart/form-data; boundary=b",
        ),
    ],
    ids=["binary", "multipart"],
)
def test_request_event_stores_only_type_and_size_of_files_and_binary(
    rf: RequestFactory, data: bytes, content_type: str
) -> None:
    request = rf.post("/", data, content_type)

    event = IncomingEventBuilder().build_request_event(request)

    assert event["data"]["body"] == {
        "content_type": content_type.partition(";")[0],
        "size": len(data),
    }


# Under 64 KB, json.loads refuses the deeper one and masking the shallower one hits the limit.
@pytest.mark.parametrize("depth", [5_000, 30_000])
def test_request_event_stores_only_type_and_size_of_deeply_nested_json(
    rf: RequestFactory, depth: int
) -> None:
    data = "[" * depth + "]" * depth
    request = rf.post("/", data, "application/json")

    event = IncomingEventBuilder().build_request_event(request)

    assert event["data"]["body"] == {"content_type": "application/json", "size": len(data)}


# Python's json accepts these, but they crash the request (digit limit) or Postgres refuses the row.
@pytest.mark.parametrize(
    "data",
    ["1" * 5_000, '{"x": NaN}', '{"x": Infinity}', '{"x": 1e400}', '{"x": "\\ud800"}'],
    ids=["too_many_digits", "nan", "infinity", "overflow", "lone_surrogate"],
)
def test_request_event_stores_only_type_and_size_of_json_postgres_refuses(
    rf: RequestFactory, data: str
) -> None:
    request = rf.post("/", data, "application/json")

    event = IncomingEventBuilder().build_request_event(request)

    assert event["data"]["body"] == {"content_type": "application/json", "size": len(data)}


def test_request_event_truncates_body_over_limit(rf: RequestFactory) -> None:
    data = json.dumps({"text": "a" * IncomingEventBuilder.max_body_bytes})
    request = rf.post("/", data, "application/json")

    event = IncomingEventBuilder().build_request_event(request)

    assert event["data"]["body"] == {
        "content_type": "application/json",
        "size": len(data),
        "truncated": True,
    }


def test_request_event_truncates_body_django_refuses_to_read(
    rf: RequestFactory, settings: Settings
) -> None:
    settings.DATA_UPLOAD_MAX_MEMORY_SIZE = 10
    data = json.dumps({"text": "a" * 20})
    request = rf.post("/", data, "application/json")

    event = IncomingEventBuilder().build_request_event(request)

    assert event["data"]["body"] == {
        "content_type": "application/json",
        "size": len(data),
        "truncated": True,
    }


def test_request_event_replaces_nul_characters(rf: RequestFactory) -> None:
    request = rf.post("/a%00b/", json.dumps({"name": "x\x00y"}), "application/json")

    event = IncomingEventBuilder().build_request_event(request)

    assert "\x00" not in event["path"]
    assert "\x00" not in event["data"]["body"]["name"]


def test_response_event_records_the_response(rf: RequestFactory) -> None:
    request = rf.get("/accounts/login/", headers={"X-Request-ID": "req-1"})
    response = JsonResponse({"ok": True}, status=HTTPStatus.CREATED)

    event = IncomingEventBuilder().build_response_event(request, response, duration_ms=12)

    assert {key: value for key, value in event.items() if key != "logged_at"} == {
        "type": EventType.RESPONSE,
        "request_id": "req-1",
        "url_name": ConsumerLoginView.url_name,
        "method": "GET",
        "path": "/accounts/login/",
        "data": {"body": {"ok": True}},
        "headers": {"Content-Type": "application/json"},
        "status": HTTPStatus.CREATED,
        "duration_ms": 12,
        "error": None,
        "user_id": None,
        "additional_info": {"ip": "127.0.0.1"},
    }
    assert datetime.fromisoformat(event["logged_at"]) <= timezone.now()


def test_response_event_masks_headers_and_json_body(rf: RequestFactory, masked: str) -> None:
    response = JsonResponse({"access_token": "abc", "expires_in": 60})
    response["X-Api-Key"] = "k"

    event = IncomingEventBuilder().build_response_event(rf.get("/"), response, duration_ms=1)

    assert event["headers"]["X-Api-Key"] == masked
    assert event["data"]["body"] == {"access_token": masked, "expires_in": 60}


def test_response_event_stores_only_type_and_size_of_html(rf: RequestFactory) -> None:
    response = HttpResponse("<p>Salaam</p>")

    event = IncomingEventBuilder().build_response_event(rf.get("/"), response, duration_ms=1)

    assert event["data"]["body"] == {"content_type": "text/html", "size": len(response.content)}


def test_response_event_stores_only_type_of_streamed_body(rf: RequestFactory) -> None:
    response = StreamingHttpResponse(iter([b"data: hi\n\n"]), content_type="text/event-stream")

    event = IncomingEventBuilder().build_response_event(rf.get("/"), response, duration_ms=1)

    assert event["data"]["body"] == {"content_type": "text/event-stream"}


def test_response_event_records_logged_in_user(rf: RequestFactory) -> None:
    request = rf.get("/")
    request.user = Mock(is_authenticated=True, pk=7)

    event = IncomingEventBuilder().build_response_event(request, HttpResponse(), duration_ms=1)

    assert event["user_id"] == 7


def test_response_event_records_user_who_logged_out(rf: RequestFactory) -> None:
    request = rf.post("/accounts/logout/")
    request.user = AnonymousUser()
    remember_logged_out_user(sender=None, request=request, user=Mock(pk=7))

    event = IncomingEventBuilder().build_response_event(request, HttpResponse(), duration_ms=1)

    assert event["user_id"] == 7


def test_response_event_has_no_user_when_anonymous(rf: RequestFactory) -> None:
    request = rf.get("/")
    request.user = AnonymousUser()

    event = IncomingEventBuilder().build_response_event(request, HttpResponse(), duration_ms=1)

    assert event["user_id"] is None


def test_response_event_records_error_without_locals(rf: RequestFactory) -> None:
    request = rf.get("/")
    try:
        local_value = "never-stored"
        raise ValueError(local_value)
    except ValueError:
        remember_request_error(sender=None, request=request)

    event = IncomingEventBuilder().build_response_event(
        request, HttpResponse(status=HTTPStatus.INTERNAL_SERVER_ERROR), duration_ms=1
    )

    assert event["error"]["error_type"] == "ValueError"
    assert event["error"]["traceback"][0]["exc_type"] == "ValueError"
    assert "never-stored" not in json.dumps(event["error"]["traceback"][0]["frames"])


def test_response_event_replaces_nul_characters(rf: RequestFactory) -> None:
    response = JsonResponse({"name": "x\x00y"})

    event = IncomingEventBuilder().build_response_event(rf.get("/"), response, duration_ms=1)

    assert "\x00" not in event["data"]["body"]["name"]


def test_request_event_masks_url_token_in_referer(rf: RequestFactory, masked: str) -> None:
    request = rf.get(
        "/", headers={"Referer": "https://muminmate.example/accounts/verify/MQ/live-token/"}
    )

    event = IncomingEventBuilder().build_request_event(request)

    assert event["headers"]["Referer"] == f"https://muminmate.example/accounts/verify/MQ/{masked}/"


def test_response_event_masks_url_token_in_location(rf: RequestFactory, masked: str) -> None:
    response = HttpResponseRedirect("/accounts/password-reset/MQ/live-token/")

    event = IncomingEventBuilder().build_response_event(rf.get("/"), response, duration_ms=1)

    assert event["headers"]["Location"] == f"/accounts/password-reset/MQ/{masked}/"


@pytest.mark.parametrize(
    "referer", ["http://[", "http://x]/a"], ids=["open_bracket", "close_bracket"]
)
def test_request_event_masks_unparseable_referer(
    rf: RequestFactory, masked: str, referer: str
) -> None:
    request = rf.get("/", headers={"Referer": referer})

    event = IncomingEventBuilder().build_request_event(request)

    assert event["headers"]["Referer"] == masked
