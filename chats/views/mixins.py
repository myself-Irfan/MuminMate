from typing import Any

from django.db.models import QuerySet
from django.http import Http404

from chats.http import HtmxHttpRequest
from chats.models import Thread
from chats.services.thread_service import ThreadService


class OwnedThreadMixin:
    request: HtmxHttpRequest
    kwargs: dict[str, Any]

    # Django's SingleObjectMixin hook; another user's thread is a 404, like a missing one.
    def get_object(self, queryset: QuerySet[Thread] | None = None) -> Thread:
        thread = ThreadService().get_thread(self.request.user, self.kwargs["public_id"])
        if thread is None:
            raise Http404
        return thread
