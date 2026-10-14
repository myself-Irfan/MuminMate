from http import HTTPStatus

import structlog
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


# k8s polls these every few seconds: keep only failures.
def drop_successful_probes(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    is_routine_event = event_dict.get("event") in {"request_started", "request_finished"}
    has_failed = "code" in event_dict and event_dict["code"] >= HTTPStatus.BAD_REQUEST
    if event_dict.get("is_probe") and is_routine_event and not has_failed:
        raise structlog.DropEvent
    return event_dict
