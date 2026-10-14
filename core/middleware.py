import re
import uuid
from collections.abc import Callable

from django.http import HttpRequest, HttpResponse


# First in MIDDLEWARE: rewrites META before anything reads request.headers.
class RequestIDMiddleware:
    header = "X-Request-ID"
    meta_key = "HTTP_X_REQUEST_ID"
    valid_id = re.compile(r"[A-Za-z0-9._-]{1,128}")

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        request_id = request.META.get(self.meta_key, "")
        if not self.valid_id.fullmatch(request_id):
            request_id = str(uuid.uuid4())
        request.META[self.meta_key] = request_id
        # One ID per request: django-structlog would log a client's correlation ID unchecked.
        request.META.pop("HTTP_X_CORRELATION_ID", None)

        response = self.get_response(request)
        response[self.header] = request_id
        return response
