from typing import Any

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.generic import FormView
from django_htmx.http import trigger_client_event

from chats.forms import MessageForm
from chats.http import HtmxHttpRequest
from chats.models import Thread
from chats.services.message_service import MessageService
from chats.views.chat_views import ThreadDetailView
from chats.views.mixins import OwnedThreadMixin
from core.mixins import UnprocessableFormMixin


class MessageCreateView(
    OwnedThreadMixin, UnprocessableFormMixin[MessageForm], FormView[MessageForm]
):
    request: HtmxHttpRequest
    thread: Thread
    form_class = MessageForm
    http_method_names = ("post",)
    url_name = "message_create"

    # FormView types post()'s request as HttpRequest; self.request carries the narrowed type.
    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        self.thread = self.get_object()
        return super().post(request, *args, **kwargs)

    def get_template_names(self) -> list[str]:
        if self.request.htmx:
            return ["chats/partials/composer.html"]
        return ["chats/thread_detail.html"]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        if not self.request.htmx:
            kwargs["chat_messages"] = MessageService().get_messages(self.thread)
        return super().get_context_data(thread=self.thread, **kwargs)

    def form_valid(self, form: MessageForm) -> HttpResponse:
        conversation = MessageService()
        message = conversation.send(self.thread, form.cleaned_data["content"])
        reply = conversation.reply(self.thread)
        if not self.request.htmx:
            return redirect(ThreadDetailView.url_name, public_id=self.thread.public_id)
        # Both messages ride out of band; the box itself is replaced.
        return trigger_client_event(
            render(
                self.request,
                "chats/partials/composer.html",
                {"thread": self.thread, "form": MessageForm(), "new_messages": [message, reply]},
            ),
            "threads-changed",
        )
