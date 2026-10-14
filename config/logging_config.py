from typing import Any

import structlog
from structlog.tracebacks import ExceptionDictTransformer
from structlog.typing import Processor

from config.env import LogSettings
from core.log_processors import drop_successful_probes, mask_sensitive


def build_shared_processors() -> list[Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.CallsiteParameterAdder(
            [
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            ]
        ),
    ]


def build_logging(log_settings: LogSettings) -> dict[str, Any]:
    render_exception: Processor
    renderer: Processor
    if log_settings.format == "json":
        # structlog defaults to logging locals, which can hold passwords.
        render_exception = structlog.processors.ExceptionRenderer(
            ExceptionDictTransformer(show_locals=False)
        )
        renderer = structlog.processors.JSONRenderer()
    else:
        render_exception = structlog.processors.format_exc_info
        renderer = structlog.dev.ConsoleRenderer()
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "structlog": {
                "()": structlog.stdlib.ProcessorFormatter,
                "foreign_pre_chain": build_shared_processors(),
                "processors": [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    render_exception,
                    mask_sensitive,
                    renderer,
                ],
            }
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "structlog",
            },
            # [] would fall back to logging.lastResort.
            "null": {"class": "logging.NullHandler"},
        },
        "root": {"handlers": ["stdout"], "level": log_settings.level},
        "loggers": {
            # Drops Django's default handlers; lines go via root.
            "django": {"handlers": [], "level": log_settings.level, "propagate": True},
            # Duplicates of django-structlog's request events.
            "django.request": {"handlers": ["null"], "propagate": False},
            "django.server": {"handlers": ["null"], "propagate": False},
            # uvicorn sets up its own plain-text handler before Django loads.
            "uvicorn": {"handlers": [], "level": log_settings.level, "propagate": True},
            # Else it propagates and logs unmasked query strings.
            "uvicorn.access": {"handlers": [], "propagate": False},
        },
    }


def configure_structlog() -> None:
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *build_shared_processors(),
            # Needs is_probe, added by merge_contextvars.
            drop_successful_probes,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
