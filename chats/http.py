from urllib.parse import urlsplit
from uuid import UUID

from django.urls import Resolver404, resolve
from django_htmx.middleware import HtmxDetails

from users.http import AuthenticatedHttpRequest


# django-htmx's documented typing pattern: HtmxMiddleware sets `htmx` on every request.
class HtmxHttpRequest(AuthenticatedHttpRequest):
    htmx: HtmxDetails


# htmx sends the page's URL; the open thread is the one that page shows.
def get_open_thread_id(htmx: HtmxDetails) -> UUID | None:
    url = htmx.current_url_abs_path
    if url is None:
        return None
    try:
        return resolve(urlsplit(url).path).kwargs.get("public_id")
    except Resolver404:
        return None
