import json
from collections.abc import Mapping
from typing import Any
from urllib.parse import parse_qs, urlsplit

from django.core.exceptions import RequestDataTooBig
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.urls import Resolver404, resolve
from django.utils import timezone
from structlog.tracebacks import ExceptionDictTransformer

from audit.enums import EventType, RequestAttribute
from audit.models import IncomingRequestResponseEvent
from core.client_ip import get_client_ip
from core.masking import DataMasker
from core.middleware import RequestIDMiddleware
from core.url_tokens import find_url_token


# Translates a request and its response into masked rows; touches no db or broker.
class IncomingEventBuilder:
    max_body_bytes = 64 * 1024
    masker = DataMasker()
    traceback_transformer = ExceptionDictTransformer(show_locals=False)
    url_headers = frozenset({"referer", "location"})

    def build_request_event(self, request: HttpRequest) -> dict[str, Any]:
        return self._event_without_nul(
            {
                **self._get_request_fields(request, EventType.REQUEST),
                "data": self._get_data(
                    params=self.masker.mask(dict(request.GET.lists())),
                    body=self._get_request_body(request),
                ),
                "headers": self._get_masked_headers(request.headers),
            }
        )

    def build_response_event(
        self, request: HttpRequest, response: HttpResponseBase, duration_ms: int
    ) -> dict[str, Any]:
        return self._event_without_nul(
            {
                **self._get_request_fields(request, EventType.RESPONSE),
                "data": self._get_data(body=self._get_response_body(response)),
                "headers": self._get_masked_headers(response.headers),
                "status": response.status_code,
                "duration_ms": duration_ms,
                "error": self._get_error(request),
                "user_id": self._get_user_id(request),
            }
        )

    def _get_request_fields(self, request: HttpRequest, event_type: EventType) -> dict[str, Any]:
        return {
            "type": event_type,
            "request_id": request.headers.get(RequestIDMiddleware.header, ""),
            "url_name": self._get_url_name(request),
            "method": (request.method or "")[: IncomingRequestResponseEvent.max_method_length],
            "path": self._get_masked_path(request),
            "additional_info": {"ip": get_client_ip(request)},
            "logged_at": timezone.now().isoformat(),
        }

    def _get_data(self, params: dict[str, Any] | None = None, body: Any = None) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if params:
            data["params"] = params
        if body is not None:
            data["body"] = body
        return data

    def _get_url_name(self, request: HttpRequest) -> str:
        try:
            return resolve(request.path_info).view_name
        except Resolver404:
            return ""

    # resolve() needs path_info, without the script prefix the stored path keeps.
    def _get_masked_path(self, request: HttpRequest) -> str:
        return self._mask_url_token(request.path, request.path_info)

    # These two can hold a whole link: same-origin referrers, CommonMiddleware's slash redirect.
    def _get_masked_headers(self, headers: Mapping[str, str]) -> dict[str, Any]:
        masked: dict[str, Any] = self.masker.mask(dict(headers))
        for key, value in masked.items():
            if key.lower() in self.url_headers and isinstance(value, str):
                masked[key] = self._mask_url_header(value)
        return masked

    # A URL we can't parse can't be checked for a token either, so it's masked whole.
    def _mask_url_header(self, url: str) -> str:
        try:
            path = urlsplit(url).path
        except ValueError:
            return self.masker.replacement
        return self._mask_url_token(url, path)

    def _mask_url_token(self, url: str, path: str) -> str:
        token = find_url_token(path)
        return url.replace(token, self.masker.replacement) if token else url

    def _get_request_body(self, request: HttpRequest) -> Any:
        content_type = request.content_type or ""
        try:
            body = request.body
        except RequestDataTooBig:
            size = int(request.META.get("CONTENT_LENGTH") or 0)
            return self._describe_truncated_body(content_type, size)
        return self._get_body(body, content_type)

    def _get_body(self, body: bytes, content_type: str) -> Any:
        if not body:
            return None
        if len(body) > self.max_body_bytes:
            return self._describe_truncated_body(content_type, len(body))
        if content_type.startswith("multipart/") or content_type == "text/html":
            return self._describe_body(content_type, len(body))
        try:
            text = body.decode()
        except UnicodeDecodeError:
            return self._describe_body(content_type, len(body))
        if content_type == "application/x-www-form-urlencoded":
            return self.masker.mask(parse_qs(text, keep_blank_values=True))
        # Text we can't parse can't be masked either, so only its type and size are kept.
        try:
            value = json.loads(text)
            # Python accepts NaN, Infinity and lone surrogates; jsonb refuses them.
            json.dumps(value, allow_nan=False, ensure_ascii=False).encode()
            return self.masker.mask(value)
        except (ValueError, RecursionError):
            return self._describe_body(content_type, len(body))

    def _get_response_body(self, response: HttpResponseBase) -> Any:
        content_type = response.get("Content-Type", "").partition(";")[0].strip()
        if isinstance(response, HttpResponse):
            return self._get_body(response.content, content_type)
        # Streamed: the body is sent after the middleware returns.
        return {"content_type": content_type}

    def _get_error(self, request: HttpRequest) -> dict[str, Any] | None:
        error: BaseException | None = getattr(request, RequestAttribute.ERROR, None)
        if error is None:
            return None
        return {
            "error_type": type(error).__name__,
            "traceback": self.traceback_transformer((type(error), error, error.__traceback__)),
        }

    def _get_user_id(self, request: HttpRequest) -> int | None:
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            return int(user.pk)
        user_id: int | None = getattr(request, RequestAttribute.LOGGED_OUT_USER_ID, None)
        return user_id

    def _describe_body(self, content_type: str, size: int) -> dict[str, Any]:
        return {"content_type": content_type, "size": size}

    def _describe_truncated_body(self, content_type: str, size: int) -> dict[str, Any]:
        return {**self._describe_body(content_type, size), "truncated": True}

    # Postgres refuses NUL in text and jsonb.
    def _event_without_nul(self, event: dict[str, Any]) -> dict[str, Any]:
        return {key: self._without_nul(value) for key, value in event.items()}

    def _without_nul(self, value: Any) -> Any:
        if isinstance(value, str):
            return value.replace("\x00", "\ufffd")
        if isinstance(value, dict):
            return {self._without_nul(key): self._without_nul(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._without_nul(item) for item in value]
        return value
