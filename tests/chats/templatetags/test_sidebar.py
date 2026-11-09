import pytest
from django.template import Context
from django.test import RequestFactory
from django.urls import resolve

from chats.models import Thread
from chats.templatetags.sidebar import sidebar
from users.models import User


@pytest.mark.usefixtures("page_size_two")
def test_sidebar_tag_pages_after_valid_cursor(rf: RequestFactory, consumer_user: User) -> None:
    oldest, middle, _ = (
        Thread.objects.create(user=consumer_user, title=title) for title in ("A", "B", "C")
    )
    request = rf.get("/", {"after": str(middle.public_id)})
    request.user = consumer_user

    assert sidebar(Context({"request": request})).threads == [oldest]


@pytest.mark.usefixtures("thread")
def test_sidebar_tag_ignores_invalid_cursor(rf: RequestFactory, consumer_user: User) -> None:
    request = rf.get("/", {"after": "not-a-uuid"})
    request.user = consumer_user

    assert len(sidebar(Context({"request": request})).threads) == 1


def test_sidebar_tag_takes_open_id_from_url(
    rf: RequestFactory, consumer_user: User, thread: Thread
) -> None:
    request = rf.get(f"/chats/{thread.public_id}/")
    request.user = consumer_user
    request.resolver_match = resolve(f"/chats/{thread.public_id}/")

    assert sidebar(Context({"request": request})).open_id == thread.public_id


@pytest.mark.parametrize("path", ["/", None], ids=["page-without-thread", "no-resolver-match"])
def test_sidebar_tag_has_no_open_id_off_a_thread_page(
    rf: RequestFactory, consumer_user: User, path: str | None
) -> None:
    request = rf.get("/")
    request.user = consumer_user
    request.resolver_match = resolve(path) if path else None

    assert sidebar(Context({"request": request})).open_id is None
