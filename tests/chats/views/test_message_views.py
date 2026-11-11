import json
from http import HTTPStatus

import pytest
from django.test import Client
from pytest_django.asserts import assertContains, assertRedirects, assertTemplateUsed

from chats.enums import MessageRole
from chats.models import Message, Thread


@pytest.fixture
def send_path(thread: Thread) -> str:
    return f"/chats/{thread.public_id}/messages/"


@pytest.fixture
def htmx_on_thread_headers(thread: Thread) -> dict[str, str]:
    return {"HX-Request": "true", "HX-Current-URL": f"http://testserver/chats/{thread.public_id}/"}


def test_send_for_htmx_returns_fresh_box_and_both_new_messages(
    consumer_client: Client,
    thread: Thread,
    send_path: str,
    htmx_on_thread_headers: dict[str, str],
) -> None:
    response = consumer_client.post(
        send_path, {"content": "Still anxious"}, headers=htmx_on_thread_headers
    )

    assert list(thread.messages.order_by("id").values_list("role", "content")) == [
        (MessageRole.USER, "Still anxious"),
        (MessageRole.ASSISTANT, "You said: Still anxious"),
    ]
    assertTemplateUsed(response, "chats/partials/composer.html")
    assertContains(response, 'hx-swap-oob="beforeend:#chat-messages"')
    assertContains(response, "Still anxious</div></li>")
    assertContains(response, "You said: Still anxious")
    assertContains(response, ">\n</textarea>")
    assert json.loads(response["HX-Trigger"]) == {"threads-changed": {}}


def test_send_without_htmx_redirects_to_thread(
    consumer_client: Client, thread: Thread, send_path: str
) -> None:
    response = consumer_client.post(send_path, {"content": "Still anxious"})

    assertRedirects(response, f"/chats/{thread.public_id}/", fetch_redirect_response=False)
    assert thread.messages.count() == 2


@pytest.mark.parametrize("content", ["", "   "], ids=["empty", "spaces"])
def test_send_blank_for_htmx_returns_422_box_and_saves_nothing(
    consumer_client: Client, send_path: str, htmx_on_thread_headers: dict[str, str], content: str
) -> None:
    response = consumer_client.post(send_path, {"content": content}, headers=htmx_on_thread_headers)

    assertTemplateUsed(response, "chats/partials/composer.html")
    assertContains(response, "Write a message.", status_code=HTTPStatus.UNPROCESSABLE_ENTITY)
    assert "HX-Trigger" not in response
    assert not Message.objects.exists()


@pytest.mark.usefixtures("message_max_length_five")
def test_send_too_long_without_htmx_returns_422_page_keeping_text(
    consumer_client: Client, send_path: str
) -> None:
    response = consumer_client.post(send_path, {"content": "123456"})

    assertTemplateUsed(response, "chats/thread_detail.html")
    assertContains(response, "at most 5 characters", status_code=HTTPStatus.UNPROCESSABLE_ENTITY)
    assertContains(response, ">\n123456</textarea>", status_code=HTTPStatus.UNPROCESSABLE_ENTITY)
    assert not Message.objects.exists()


def test_send_returns_404_for_other_users_thread(
    consumer_client: Client, other_thread: Thread
) -> None:
    response = consumer_client.post(
        f"/chats/{other_thread.public_id}/messages/", {"content": "Mine"}
    )

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert not Message.objects.exists()


def test_send_refuses_get(consumer_client: Client, send_path: str) -> None:
    response = consumer_client.get(send_path)

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
