from http import HTTPStatus
from unittest.mock import Mock

import pytest
import structlog
from django.test import RequestFactory

from core.log_processors import (
    drop_successful_probes,
    mask_sensitive,
    mask_url_tokens,
    move_exception_to_exc_info,
)
from core.masking import DataMasker


def test_url_token_left_alone_without_request() -> None:
    event = {"event": "task_started"}

    assert mask_url_tokens(None, "info", dict(event)) == event


def test_url_token_left_alone_when_path_not_found() -> None:
    event = {"event": "request_started", "request": "GET /nope/abc123/"}

    assert mask_url_tokens(None, "info", dict(event)) == event


def test_url_token_left_alone_when_route_has_no_token() -> None:
    event = {"event": "request_started", "request": "GET /accounts/login/"}

    assert mask_url_tokens(None, "info", dict(event)) == event


def test_url_token_masked_in_event_and_request() -> None:
    event = {
        "event": "Forbidden: /accounts/verify/MQ/abc123/",
        "request": "POST /accounts/verify/MQ/abc123/?next=/",
    }

    masked = mask_url_tokens(None, "info", event)

    assert (masked["event"], masked["request"]) == (
        "Forbidden: /accounts/verify/MQ/*****/",
        "POST /accounts/verify/MQ/*****/?next=/",
    )


def test_url_token_path_read_from_stdlib_record(rf: RequestFactory) -> None:
    event = {
        "event": "Forbidden (CSRF cookie not set.): /accounts/verify/MQ/abc123/",
        "_record": Mock(request=rf.post("/accounts/verify/MQ/abc123/")),
    }

    masked = mask_url_tokens(None, "warning", event)

    assert masked["event"] == "Forbidden (CSRF cookie not set.): /accounts/verify/MQ/*****/"


def test_mask_sensitive_masks_fields_and_request_query() -> None:
    event = {"event": "request_started", "request": "GET /api/x?token=t&a=1", "password": "p"}

    assert mask_sensitive(None, "info", event) == {
        "event": "request_started",
        "request": f"GET /api/x?token={DataMasker.replacement}&a=1",
        "password": DataMasker.replacement,
    }


def test_probe_without_code_dropped() -> None:
    event = {"event": "request_started", "is_probe": True}

    with pytest.raises(structlog.DropEvent):
        drop_successful_probes(None, "info", event)


@pytest.mark.parametrize("code", [HTTPStatus.OK, HTTPStatus.NOT_MODIFIED])
def test_successful_probe_dropped(code: HTTPStatus) -> None:
    event = {"event": "request_finished", "is_probe": True, "code": code}

    with pytest.raises(structlog.DropEvent):
        drop_successful_probes(None, "info", event)


def test_failing_probe_kept() -> None:
    event = {"event": "request_finished", "is_probe": True, "code": HTTPStatus.BAD_REQUEST}

    assert drop_successful_probes(None, "info", event) == event


def test_app_event_during_probe_kept() -> None:
    event = {"event": "db_check_failed", "is_probe": True, "error_type": "OperationalError"}

    assert drop_successful_probes(None, "error", event) == event


def test_crash_during_probe_kept() -> None:
    event = {"event": "request_failed", "is_probe": True}

    assert drop_successful_probes(None, "error", event) == event


def test_other_request_kept() -> None:
    event = {"event": "request_finished", "code": HTTPStatus.OK}

    assert drop_successful_probes(None, "info", event) == event


def test_exception_object_moved_to_exc_info() -> None:
    error = ValueError("boom")

    event = move_exception_to_exc_info(None, "error", {"exception": error, "exc_info": True})

    assert event == {"exc_info": error}


def test_formatted_exception_left_alone() -> None:
    event = {"exception": "Traceback ..."}

    assert move_exception_to_exc_info(None, "error", event) == event
