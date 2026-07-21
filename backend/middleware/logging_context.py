import time

import structlog.contextvars
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from backend.auth.services._helpers import decode_user_id
from backend.config import settings
from backend.logger import get_logger

logger = get_logger(__name__)


class LoggingContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        structlog.contextvars.clear_contextvars()

        query = self._sanitize(dict(request.query_params))
        structlog.contextvars.bind_contextvars(
            method=request.method,
            path=request.url.path,
            **({"query": query} if query else {}),
        )
        self._bind_ip(request)
        self._bind_user(request)

        logger.info("request started")
        start = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.info(
                "request finished", status_code=response.status_code, duration_ms=duration_ms
            )
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - start) * 1000, 1)
            logger.error("request failed", exc_info=True, duration_ms=duration_ms)
            raise
        finally:
            structlog.contextvars.clear_contextvars()

    @staticmethod
    def _bind_ip(request: Request) -> None:
        forwarded = request.headers.get("x-forwarded-for")
        ip = (
            forwarded.split(",")[0].strip()
            if forwarded
            else (request.client.host if request.client else None)
        )
        structlog.contextvars.bind_contextvars(ip=ip)

    @staticmethod
    def _bind_user(request: Request) -> None:
        auth = request.headers.get("Authorization")
        if not auth or not auth.lower().startswith("bearer "):
            return
        token = auth.split(" ", 1)[1]
        user_id = decode_user_id(request, token)
        if user_id is not None:
            structlog.contextvars.bind_contextvars(user_id=user_id)

    @staticmethod
    def _sanitize(data: dict) -> dict:
        return {
            k: "***"
            if k.lower() in settings.masking_keys_set
            else (LoggingContextMiddleware._sanitize(v) if isinstance(v, dict) else v)
            for k, v in data.items()
        }
