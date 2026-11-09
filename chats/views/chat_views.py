from typing import Any

from django.views.generic import DetailView, TemplateView

from chats.http import HtmxHttpRequest
from chats.models import Thread
from chats.services.thread_service import ThreadService
from chats.views.mixins import OwnedThreadMixin


class ChatHomeView(TemplateView):
    request: HtmxHttpRequest
    template_name = "chats/home.html"
    url_name = "home"

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        return super().get_context_data(
            has_threads=ThreadService().exists_threads(self.request.user), **kwargs
        )


class ThreadDetailView(OwnedThreadMixin, DetailView[Thread]):
    request: HtmxHttpRequest
    template_name = "chats/thread_detail.html"
    url_name = "thread_detail"
