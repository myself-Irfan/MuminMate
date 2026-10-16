import io
import json
import logging
import re
from http import HTTPStatus
from typing import NoReturn
from unittest.mock import Mock

import pytest
import structlog
import uvicorn.config
from django.test import Client

from config.env import LogSettings
from core.masking import DataMasker
from tests.logging_support import json_lines, route_logs_to_buffer
from users.models import User

pytestmark = pytest.mark.usefixtures("restore_logging")


def _raise_chained_error() -> NoReturn:
    try:
        raise ValueError("Key (email)=(alice@example.com) already exists.")
    except ValueError as error:
        raise RuntimeError("save failed") from error


def _log_chained_error(log_settings: LogSettings) -> io.StringIO:
    buffer = route_logs_to_buffer(log_settings)
    try:
        _raise_chained_error()
    except RuntimeError:
        structlog.get_logger("tests").exception("thing_failed")
    return buffer


def _caught_chained_error() -> RuntimeError:
    try:
        _raise_chained_error()
    except RuntimeError as error:
        return error


def _log_failed_task(log_settings: LogSettings) -> io.StringIO:
    buffer = route_logs_to_buffer(log_settings)
    structlog.get_logger("tests").exception("task_failed", exception=_caught_chained_error())
    return buffer


def test_json_line_carries_event_and_context_keys() -> None:
    buffer = route_logs_to_buffer(LogSettings(level="INFO", format="json"))

    structlog.get_logger("tests").warning("thing_failed", user_id=18)

    line = json.loads(buffer.getvalue())
    assert line["event"] == "thing_failed"
    assert line["user_id"] == 18
    assert line["level"] == "warning"
    assert line["logger"] == "tests"
    assert line["timestamp"].endswith("Z")
    assert line["func_name"] == "test_json_line_carries_event_and_context_keys"


def test_json_line_for_stdlib_logger() -> None:
    buffer = route_logs_to_buffer(LogSettings(level="INFO", format="json"))

    logging.getLogger("django.security").warning("csrf_failed")

    line = json.loads(buffer.getvalue())
    assert line["event"] == "csrf_failed"
    assert line["logger"] == "django.security"
    assert line["level"] == "warning"


def test_console_line_is_readable_key_values() -> None:
    buffer = route_logs_to_buffer(LogSettings(level="INFO", format="console"))

    structlog.get_logger("tests").warning("thing_failed", user_id=18, api_key="k")

    line = re.sub(r"\x1b\[[0-9;]*m", "", buffer.getvalue())
    assert "thing_failed" in line
    assert "user_id=18" in line
    assert f"api_key={DataMasker.replacement}" in line


def test_level_drops_lower_events() -> None:
    buffer = route_logs_to_buffer(LogSettings(level="WARNING", format="json"))

    structlog.get_logger("tests").info("thing_happened")

    assert buffer.getvalue() == ""


def test_json_exception_is_structured_with_its_cause() -> None:
    buffer = _log_chained_error(LogSettings(level="INFO", format="json"))

    [error, cause] = json.loads(buffer.getvalue())["exception"]
    assert error["exc_type"] == "RuntimeError"
    assert cause["exc_type"] == "ValueError"
    assert cause["is_cause"] is True
    assert "_raise_chained_error" in [frame["name"] for frame in cause["frames"]]


def test_json_exception_keeps_message() -> None:
    buffer = _log_chained_error(LogSettings(level="INFO", format="json"))

    [_, cause] = json.loads(buffer.getvalue())["exception"]
    assert cause["exc_value"] == "Key (email)=(alice@example.com) already exists."


def test_json_exception_omits_locals() -> None:
    buffer = _log_chained_error(LogSettings(level="INFO", format="json"))

    exception = json.loads(buffer.getvalue())["exception"]
    assert all("locals" not in frame for entry in exception for frame in entry["frames"])


def test_console_exception_is_text_traceback() -> None:
    buffer = _log_chained_error(LogSettings(level="INFO", format="console"))

    assert "Traceback (most recent call last)" in buffer.getvalue()
    assert "ValueError: Key (email)=(alice@example.com) already exists." in buffer.getvalue()


def test_json_exception_passed_as_key_is_structured() -> None:
    buffer = _log_failed_task(LogSettings(level="INFO", format="json"))

    [error, cause] = json.loads(buffer.getvalue())["exception"]
    assert error["exc_type"] == "RuntimeError"
    assert cause["exc_type"] == "ValueError"


def test_console_exception_passed_as_key_is_text_traceback() -> None:
    buffer = _log_failed_task(LogSettings(level="INFO", format="console"))

    assert "Traceback (most recent call last)" in buffer.getvalue()
    assert "RuntimeError: save failed" in buffer.getvalue()


@pytest.mark.django_db
def test_request_events_carry_request_id(client: Client, json_logs: io.StringIO) -> None:
    response = client.get("/accounts/login/")

    lines = json_lines(json_logs)
    assert [line["event"] for line in lines] == ["request_started", "request_finished"]
    assert {line["request_id"] for line in lines} == {response["X-Request-ID"]}
    assert lines[1]["code"] == HTTPStatus.OK
    assert all("is_probe" not in line for line in lines)


@pytest.mark.django_db
def test_request_finished_carries_user_id(
    client: Client, consumer_user: User, json_logs: io.StringIO
) -> None:
    client.force_login(consumer_user)

    client.get("/")

    [finished] = [line for line in json_lines(json_logs) if line["event"] == "request_finished"]
    assert finished["user_id"] == consumer_user.pk


@pytest.mark.urls("tests.urls")
def test_crash_logged_once_as_request_failed(json_logs: io.StringIO) -> None:
    client = Client(raise_request_exception=False)

    response = client.get("/test/crash")

    lines = json_lines(json_logs)
    [failed] = [line for line in lines if line["event"] == "request_failed"]
    assert failed["request_id"] == response["X-Request-ID"]
    assert "exception" in failed
    assert not any(line["logger"] == "django.request" for line in lines)


def test_successful_health_probe_not_logged(client: Client, json_logs: io.StringIO) -> None:
    client.get("/api/health/live")

    assert json_lines(json_logs) == []


def test_failing_health_probe_logged(
    monkeypatch: pytest.MonkeyPatch, client: Client, json_logs: io.StringIO
) -> None:
    monkeypatch.setattr("core.api.HealthService.is_db_ready", Mock(return_value=False))

    client.get("/api/health/ready")

    [finished] = json_lines(json_logs)
    assert finished["event"] == "request_finished"
    assert finished["code"] == HTTPStatus.SERVICE_UNAVAILABLE
    assert finished["is_probe"] is True


# uvicorn configures its own loggers before Django loads: ours must take them over.
def test_uvicorn_lines_use_our_format() -> None:
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
    buffer = route_logs_to_buffer(LogSettings(level="INFO", format="json"))

    logging.getLogger("uvicorn.error").info("Started server process")

    [line] = json_lines(buffer)
    assert line["logger"] == "uvicorn.error"
    assert line["event"] == "Started server process"


# uvicorn logs access lines only when this finds a handler; they'd carry unmasked query strings.
def test_uvicorn_access_log_has_no_handler() -> None:
    logging.config.dictConfig(uvicorn.config.LOGGING_CONFIG)
    route_logs_to_buffer(LogSettings(level="INFO", format="json"))

    assert not logging.getLogger("uvicorn.access").hasHandlers()


@pytest.mark.parametrize("name", ["celery.app.trace", "celery.worker.strategy"])
def test_celery_task_info_lines_dropped_errors_kept(name: str) -> None:
    buffer = route_logs_to_buffer(LogSettings(level="INFO", format="json"))

    logging.getLogger(name).info("Task t[1] succeeded in 0.01s: result")
    logging.getLogger(name).error("Process cleanup failed")

    assert [line["event"] for line in json_lines(buffer)] == ["Process cleanup failed"]
