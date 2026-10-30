import sys
from typing import Any

from django.db.models import Model
from django.http import HttpRequest

from audit.enums import RequestAttribute


# Django turns a view's exception into a 500 before the middleware sees the response.
def remember_request_error(
    sender: object, request: HttpRequest | None = None, **kwargs: Any
) -> None:
    error = sys.exc_info()[1]
    if request is not None and error is not None:
        setattr(request, RequestAttribute.ERROR, error)


# The request is anonymous by the time the response row is built.
def remember_logged_out_user(
    sender: object, request: HttpRequest | None, user: Model | None, **kwargs: Any
) -> None:
    if request is not None and user is not None:
        setattr(request, RequestAttribute.LOGGED_OUT_USER_ID, user.pk)
