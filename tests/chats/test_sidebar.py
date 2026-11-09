from uuid import uuid4

import pytest

from chats.models import Thread
from chats.sidebar import get_sidebar
from users.models import User


@pytest.mark.usefixtures("page_size_two")
def test_get_sidebar_cuts_page_and_points_more_at_last_shown(consumer_user: User) -> None:
    _, middle, newest = (
        Thread.objects.create(user=consumer_user, title=title) for title in ("A", "B", "C")
    )

    sidebar = get_sidebar(consumer_user, after=None, open_id=None)

    assert sidebar.threads == [newest, middle]
    assert sidebar.next_after == middle.public_id


@pytest.mark.usefixtures("page_size_two")
def test_get_sidebar_has_no_more_when_threads_fit_page(consumer_user: User) -> None:
    older, newer = (Thread.objects.create(user=consumer_user, title=title) for title in "AB")

    sidebar = get_sidebar(consumer_user, after=None, open_id=None)

    assert sidebar.threads == [newer, older]
    assert sidebar.next_after is None


@pytest.mark.usefixtures("page_size_two")
def test_get_sidebar_continues_after_cursor(consumer_user: User) -> None:
    oldest, middle, _ = (
        Thread.objects.create(user=consumer_user, title=title) for title in ("A", "B", "C")
    )

    sidebar = get_sidebar(consumer_user, after=middle.public_id, open_id=None)

    assert sidebar.threads == [oldest]
    assert sidebar.next_after is None


def test_get_sidebar_keeps_open_id(consumer_user: User) -> None:
    open_id = uuid4()

    assert get_sidebar(consumer_user, after=None, open_id=open_id).open_id == open_id
