from http import HTTPStatus
from typing import Any
from uuid import UUID

from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import UpdateView
from django_htmx.http import HttpResponseClientRedirect, HttpResponseClientRefresh

from chats.forms import ThreadRenameForm
from chats.http import HtmxHttpRequest, get_open_thread_id
from chats.models import Thread
from chats.services.thread_service import ThreadService
from chats.sidebar import get_sidebar
from chats.views.chat_views import ChatHomeView, ThreadDetailView
from chats.views.mixins import OwnedThreadMixin


class ThreadCreateView(View):
    request: HtmxHttpRequest
    url_name = "thread_create"

    def post(self, request: HtmxHttpRequest) -> HttpResponse:
        thread = ThreadService().create(request.user)
        return redirect(ThreadDetailView.url_name, public_id=thread.public_id)


class ThreadListView(View):
    request: HtmxHttpRequest
    url_name = "thread_list"

    def get(self, request: HtmxHttpRequest) -> HttpResponse:
        try:
            after = UUID(request.GET.get("after", ""))
        except ValueError:
            return HttpResponseBadRequest()
        if not request.htmx:
            return redirect(f"{reverse(ChatHomeView.url_name)}?after={after}")
        return render(
            request,
            "chats/partials/thread_rows.html",
            {"sidebar": get_sidebar(request.user, after, get_open_thread_id(request.htmx))},
        )


class ThreadRowView(OwnedThreadMixin, View):
    request: HtmxHttpRequest
    url_name = "thread_row"

    def get(self, request: HtmxHttpRequest, public_id: UUID) -> HttpResponse:
        thread = self.get_object()
        if not request.htmx:
            return redirect(ThreadDetailView.url_name, public_id=public_id)
        return render(
            request,
            "chats/partials/thread_row.html",
            {"thread": thread, "open_id": get_open_thread_id(request.htmx)},
        )


class ThreadRenameView(OwnedThreadMixin, UpdateView[Thread, ThreadRenameForm]):
    request: HtmxHttpRequest
    form_class = ThreadRenameForm
    url_name = "thread_rename"

    def get_template_names(self) -> list[str]:
        if self.request.htmx:
            return ["chats/partials/thread_rename_form.html"]
        return ["chats/thread_rename.html"]

    # Each row's form gets its own ids: the sidebar is on the page twice (aside and drawer).
    def get_form_kwargs(self) -> dict[str, Any]:
        return {**super().get_form_kwargs(), "auto_id": f"rename-{self.object.public_id}-%s"}

    def form_invalid(self, form: ThreadRenameForm) -> HttpResponse:
        return self.render_to_response(
            self.get_context_data(form=form), status=HTTPStatus.UNPROCESSABLE_ENTITY
        )

    def form_valid(self, form: ThreadRenameForm) -> HttpResponse:
        public_id = self.object.public_id
        if not ThreadService().rename(self.request.user, public_id, form.cleaned_data["title"]):
            raise Http404
        if not self.request.htmx:
            return redirect(ThreadDetailView.url_name, public_id=public_id)
        # The open thread's title is also the page heading and tab title: reload them all.
        if get_open_thread_id(self.request.htmx) == public_id:
            return HttpResponseClientRefresh()
        return render(self.request, "chats/partials/thread_row.html", {"thread": form.instance})


class ThreadDeleteView(OwnedThreadMixin, View):
    request: HtmxHttpRequest
    url_name = "thread_delete"

    def get(self, request: HtmxHttpRequest, public_id: UUID) -> HttpResponse:
        return render(request, "chats/thread_delete.html", {"thread": self.get_object()})

    def post(self, request: HtmxHttpRequest, public_id: UUID) -> HttpResponse:
        if not ThreadService().delete(request.user, public_id):
            raise Http404
        if not request.htmx:
            return redirect(ChatHomeView.url_name)
        if get_open_thread_id(request.htmx) == public_id:
            return HttpResponseClientRedirect(reverse(ChatHomeView.url_name))
        # An empty body swapped over the row removes it.
        return HttpResponse()
