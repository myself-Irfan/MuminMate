import io
import json
import logging
import logging.config
from typing import Any

from config.env import LogSettings
from config.logging_config import build_logging


def route_logs_to_buffer(log_settings: LogSettings) -> io.StringIO:
    logging.config.dictConfig(build_logging(log_settings))
    handler = logging.getHandlerByName("stdout")
    assert isinstance(handler, logging.StreamHandler)
    buffer = io.StringIO()
    handler.setStream(buffer)
    return buffer


def json_lines(buffer: io.StringIO) -> list[dict[str, Any]]:
    return [json.loads(line) for line in buffer.getvalue().splitlines()]


def events(buffer: io.StringIO, name: str) -> list[dict[str, Any]]:
    return [line for line in json_lines(buffer) if line["event"] == name]
