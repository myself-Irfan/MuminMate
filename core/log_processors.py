from http import HTTPStatus

import structlog
from django.http import HttpRequest
from django.urls import Resolver404, resolve
from structlog.typing import EventDict, WrappedLogger

from core.masking import DataMasker


def mask_sensitive(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    masker = DataMasker()
    request = event_dict.get("request")
    if isinstance(request, str) and "?" in request:
        target, _, query = request.partition("?")
        event_dict["request"] = f"{target}?{masker.mask_query(query)}"
    masked: EventDict = masker.mask(event_dict)
    return masked


# OWASP Logging: tokens in URL paths (verification, password reset), on every channel.
def mask_url_tokens(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    path = _logged_path(event_dict)
    if path is None:
        return event_dict
    try:
        token = resolve(path).kwargs.get("token")
    except Resolver404:
        return event_dict
    if token:
        for key in ("event", "request"):
            if isinstance(event_dict.get(key), str):
                event_dict[key] = event_dict[key].replace(token, "*****")
    return event_dict


# Django's log_response puts the request in the record; django-structlog logs "METHOD /path?query".
def _logged_path(event_dict: EventDict) -> str | None:
    request = getattr(event_dict.get("_record"), "request", None)
    if isinstance(request, HttpRequest):
        return request.path_info
    logged = event_dict.get("request")
    if isinstance(logged, str) and " " in logged:
        return logged.split(" ", 1)[1].partition("?")[0]
    return None


# k8s polls these every few seconds: keep only failures.
def drop_successful_probes(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    is_routine_event = event_dict.get("event") in {"request_started", "request_finished"}
    has_failed = "code" in event_dict and event_dict["code"] >= HTTPStatus.BAD_REQUEST
    if event_dict.get("is_probe") and is_routine_event and not has_failed:
        raise structlog.DropEvent
    return event_dict


# django-structlog's task_failed passes the exception as a key, outside an except block.
def move_exception_to_exc_info(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    if isinstance(event_dict.get("exception"), BaseException):
        event_dict["exc_info"] = event_dict.pop("exception")
    return event_dict
