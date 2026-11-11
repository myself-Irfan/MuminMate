import json
from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.test import Client
from pytest_django.asserts import (
    assertContains,
    assertNotContains,
    assertRedirects,
    assertTemplateNotUsed,
    assertTemplateUsed,
)

from chats.enums import MessageRole
from chats.models import Message, Thread
from chats.services.message_service import MessageService
from users.models import User


@pytest.fixture
def htmx_headers() -> dict[str, str]:
    return {"HX-Request": "true", "HX-Current-URL": "http://testserver/"}


@pytest.fixture
def htmx_on_thread_headers(thread: Thread) -> dict[str, str]:
    return {"HX-Request": "true", "HX-Current-URL": f"http://testserver/chats/{thread.public_id}/"}


def test_create_starts_chat_with_message_and_reply_then_opens_it(
    consumer_client: Client, consumer_user: User
) -> None:
    response = consumer_client.post("/chats/new/", {"content": "  Exam stress tonight  "})

    thread = Thread.objects.get(user=consumer_user)
    assertRedirects(response, f"/chats/{thread.public_id}/", fetch_redirect_response=False)
    assert thread.title == "Exam stress tonight"
    assert list(thread.messages.order_by("id").values_list("role", "content")) == [
        (MessageRole.USER, "Exam stress tonight"),
        (MessageRole.ASSISTANT, "You said: Exam stress tonight"),
    ]


def test_create_saves_line_breaks_as_newlines(consumer_client: Client) -> None:
    consumer_client.post("/chats/new/", {"content": "Line one\r\nLine two"})

    assert Message.objects.get(role=MessageRole.USER).content == "Line one\nLine two"


@pytest.mark.parametrize("content", ["", "   "], ids=["empty", "spaces"])
def test_create_blank_returns_422_home_and_saves_nothing(
    consumer_client: Client, content: str
) -> None:
    response = consumer_client.post("/chats/new/", {"content": content})

    assertTemplateUsed(response, "chats/home.html")
    assertContains(response, "Write a message.", status_code=HTTPStatus.UNPROCESSABLE_ENTITY)
    assert not Thread.objects.exists()


@pytest.mark.usefixtures("message_max_length_five")
def test_create_too_long_returns_422_and_keeps_text(consumer_client: Client) -> None:
    response = consumer_client.post("/chats/new/", {"content": "123456"})

    assertContains(response, "at most 5 characters", status_code=HTTPStatus.UNPROCESSABLE_ENTITY)
    assertContains(response, ">\n123456</textarea>", status_code=HTTPStatus.UNPROCESSABLE_ENTITY)
    assert not Thread.objects.exists()


def test_create_refuses_get(consumer_client: Client) -> None:
    response = consumer_client.get("/chats/new/")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
    assert not Thread.objects.exists()


@pytest.mark.usefixtures("page_size_two")
def test_list_returns_next_rows_for_htmx(
    consumer_client: Client, consumer_user: User, htmx_headers: dict[str, str]
) -> None:
    first, second = (MessageService().start(consumer_user, text) for text in ("Oldest", "Middle"))

    response = consumer_client.get(f"/chats/page/?after={second.public_id}", headers=htmx_headers)

    assertTemplateUsed(response, "chats/partials/thread_rows.html")
    assertTemplateNotUsed(response, "app_base.html")
    assertContains(response, f'href="/chats/{first.public_id}/"')
    assertNotContains(response, "Middle")


@pytest.mark.usefixtures("page_size_two")
def test_list_marks_open_thread_on_later_page(
    consumer_client: Client,
    consumer_user: User,
    thread: Thread,
    htmx_on_thread_headers: dict[str, str],
) -> None:
    Message.objects.create(thread=thread, role=MessageRole.USER, content="Hi")
    second = MessageService().start(consumer_user, "Hi again")

    response = consumer_client.get(
        f"/chats/page/?after={second.public_id}", headers=htmx_on_thread_headers
    )

    assertContains(response, f'href="/chats/{thread.public_id}/" aria-current="page"')


@pytest.mark.usefixtures("page_size_two")
def test_list_without_after_returns_first_page_for_htmx(
    consumer_client: Client, consumer_user: User, htmx_headers: dict[str, str]
) -> None:
    for text in ("Oldest", "Middle", "Newest"):
        MessageService().start(consumer_user, text)

    response = consumer_client.get("/chats/page/", headers=htmx_headers)

    assertContains(response, "Newest")
    assertContains(response, "Middle")
    assertNotContains(response, "Oldest")
    assertContains(response, "Show more")


def test_list_without_after_redirects_home_without_htmx(consumer_client: Client) -> None:
    response = consumer_client.get("/chats/page/")

    assertRedirects(response, "/", fetch_redirect_response=False)


def test_list_redirects_to_home_page_without_htmx(consumer_client: Client, thread: Thread) -> None:
    response = consumer_client.get(f"/chats/page/?after={thread.public_id}")

    assertRedirects(response, f"/?after={thread.public_id}", fetch_redirect_response=False)


def test_list_refuses_invalid_after(consumer_client: Client, htmx_headers: dict[str, str]) -> None:
    response = consumer_client.get("/chats/page/?after=nope", headers=htmx_headers)

    assert response.status_code == HTTPStatus.BAD_REQUEST


def test_row_returns_row_for_htmx(
    consumer_client: Client, thread: Thread, htmx_headers: dict[str, str]
) -> None:
    response = consumer_client.get(f"/chats/{thread.public_id}/row/", headers=htmx_headers)

    assertTemplateUsed(response, "chats/partials/thread_row.html")
    assertNotContains(response, 'aria-current="page"')


def test_row_marks_open_thread(
    consumer_client: Client, thread: Thread, htmx_on_thread_headers: dict[str, str]
) -> None:
    response = consumer_client.get(
        f"/chats/{thread.public_id}/row/", headers=htmx_on_thread_headers
    )

    assertContains(response, 'aria-current="page"')


@pytest.mark.parametrize(
    "current_url_headers",
    [{}, {"HX-Current-URL": "http://testserver/nowhere/"}],
    ids=["no_current_url", "unknown_current_url"],
)
def test_row_marks_nothing_open_without_a_thread_page(
    consumer_client: Client, thread: Thread, current_url_headers: dict[str, str]
) -> None:
    response = consumer_client.get(
        f"/chats/{thread.public_id}/row/", headers={"HX-Request": "true", **current_url_headers}
    )

    assertNotContains(response, 'aria-current="page"')


def test_row_redirects_to_thread_without_htmx(consumer_client: Client, thread: Thread) -> None:
    response = consumer_client.get(f"/chats/{thread.public_id}/row/")

    assertRedirects(response, f"/chats/{thread.public_id}/", fetch_redirect_response=False)


def test_row_returns_404_for_other_users_thread(
    consumer_client: Client, other_thread: Thread, htmx_headers: dict[str, str]
) -> None:
    response = consumer_client.get(f"/chats/{other_thread.public_id}/row/", headers=htmx_headers)

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_rename_form_for_htmx_is_the_row_form(
    consumer_client: Client, thread: Thread, htmx_headers: dict[str, str]
) -> None:
    response = consumer_client.get(f"/chats/{thread.public_id}/rename/", headers=htmx_headers)

    assertTemplateUsed(response, "chats/partials/thread_rename_form.html")
    assertTemplateNotUsed(response, "app_base.html")
    assertContains(response, 'value="Exam stress"')


def test_rename_form_ids_are_unique_per_thread(
    consumer_client: Client, thread: Thread, htmx_headers: dict[str, str]
) -> None:
    response = consumer_client.get(f"/chats/{thread.public_id}/rename/", headers=htmx_headers)

    assertContains(response, f'id="rename-{thread.public_id}-title"')
    assertContains(response, f'for="rename-{thread.public_id}-title"')


def test_rename_form_without_htmx_is_a_page(consumer_client: Client, thread: Thread) -> None:
    response = consumer_client.get(f"/chats/{thread.public_id}/rename/")

    assertTemplateUsed(response, "chats/thread_rename.html")
    assertContains(response, 'value="Exam stress"')


def test_rename_form_returns_404_for_other_users_thread(
    consumer_client: Client, other_thread: Thread
) -> None:
    response = consumer_client.get(f"/chats/{other_thread.public_id}/rename/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_rename_saves_stripped_title_and_returns_row(
    consumer_client: Client, thread: Thread, htmx_headers: dict[str, str]
) -> None:
    response = consumer_client.post(
        f"/chats/{thread.public_id}/rename/", {"title": "  Sleep  "}, headers=htmx_headers
    )

    thread.refresh_from_db()
    assert thread.title == "Sleep"
    assertTemplateUsed(response, "chats/partials/thread_row.html")
    assertContains(response, ">Sleep</a>")
    assert json.loads(response["HX-Trigger"]) == {"threads-changed": {}}


def test_rename_of_open_thread_refreshes_page(
    consumer_client: Client, thread: Thread, htmx_on_thread_headers: dict[str, str]
) -> None:
    response = consumer_client.post(
        f"/chats/{thread.public_id}/rename/", {"title": "Sleep"}, headers=htmx_on_thread_headers
    )

    assert response["HX-Refresh"] == "true"


def test_rename_without_htmx_redirects_to_thread(consumer_client: Client, thread: Thread) -> None:
    response = consumer_client.post(f"/chats/{thread.public_id}/rename/", {"title": "Sleep"})

    assertRedirects(response, f"/chats/{thread.public_id}/", fetch_redirect_response=False)


@pytest.mark.parametrize("title", ["", "   "], ids=["empty", "spaces"])
def test_rename_blank_returns_422_form_and_keeps_title(
    consumer_client: Client, thread: Thread, htmx_headers: dict[str, str], title: str
) -> None:
    response = consumer_client.post(
        f"/chats/{thread.public_id}/rename/", {"title": title}, headers=htmx_headers
    )

    thread.refresh_from_db()
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assertTemplateUsed(response, "chats/partials/thread_rename_form.html")
    assertContains(response, "Enter a title.", status_code=HTTPStatus.UNPROCESSABLE_ENTITY)
    assert thread.title == "Exam stress"


def test_rename_too_long_returns_422(consumer_client: Client, thread: Thread) -> None:
    response = consumer_client.post(f"/chats/{thread.public_id}/rename/", {"title": "x" * 201})

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assertTemplateUsed(response, "chats/thread_rename.html")
    assertContains(response, "at most 200 characters", status_code=HTTPStatus.UNPROCESSABLE_ENTITY)


def test_rename_returns_404_for_other_users_thread(
    consumer_client: Client, other_thread: Thread
) -> None:
    response = consumer_client.post(f"/chats/{other_thread.public_id}/rename/", {"title": "Mine"})

    other_thread.refresh_from_db()
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert other_thread.title == "Not yours"


def test_rename_returns_404_when_thread_deleted_meanwhile(
    consumer_client: Client, thread: Thread, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("chats.views.thread_views.ThreadService.rename", Mock(return_value=False))

    response = consumer_client.post(f"/chats/{thread.public_id}/rename/", {"title": "Sleep"})

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_confirm_page_names_thread(consumer_client: Client, thread: Thread) -> None:
    response = consumer_client.get(f"/chats/{thread.public_id}/delete/")

    assertTemplateUsed(response, "chats/thread_delete.html")
    assertContains(response, "Delete this chat?")
    assertContains(response, "Exam stress")


def test_delete_confirm_page_returns_404_for_other_users_thread(
    consumer_client: Client, other_thread: Thread
) -> None:
    response = consumer_client.get(f"/chats/{other_thread.public_id}/delete/")

    assert response.status_code == HTTPStatus.NOT_FOUND


def test_delete_hides_thread_and_returns_empty_row(
    consumer_client: Client, thread: Thread, htmx_headers: dict[str, str]
) -> None:
    response = consumer_client.post(f"/chats/{thread.public_id}/delete/", headers=htmx_headers)

    thread.refresh_from_db()
    assert response.status_code == HTTPStatus.OK
    assert response.content == b""
    assert not thread.is_active
    assert json.loads(response["HX-Trigger"]) == {"threads-changed": {}}


def test_delete_of_open_thread_sends_browser_home(
    consumer_client: Client, thread: Thread, htmx_on_thread_headers: dict[str, str]
) -> None:
    response = consumer_client.post(
        f"/chats/{thread.public_id}/delete/", headers=htmx_on_thread_headers
    )

    assert response["HX-Redirect"] == "/"


def test_delete_without_htmx_redirects_home(consumer_client: Client, thread: Thread) -> None:
    response = consumer_client.post(f"/chats/{thread.public_id}/delete/")

    assertRedirects(response, "/", fetch_redirect_response=False)


def test_delete_returns_404_for_other_users_thread(
    consumer_client: Client, other_thread: Thread
) -> None:
    response = consumer_client.post(f"/chats/{other_thread.public_id}/delete/")

    other_thread.refresh_from_db()
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert other_thread.is_active


def test_delete_returns_404_when_already_deleted(consumer_client: Client, thread: Thread) -> None:
    Thread.objects.filter(pk=thread.pk).update(is_active=False)

    response = consumer_client.post(f"/chats/{thread.public_id}/delete/")

    assert response.status_code == HTTPStatus.NOT_FOUND
