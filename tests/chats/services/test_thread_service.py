from uuid import uuid4

import pytest
from django.db import IntegrityError
from pytest_django import DjangoAssertNumQueries

from chats.models import Thread
from chats.services.thread_service import ThreadService
from users.models import User


def test_create_saves_new_thread_for_user(consumer_user: User) -> None:
    thread = ThreadService().create(consumer_user)

    assert Thread.objects.get() == thread
    assert (thread.user, thread.title, thread.is_active) == (consumer_user, "New chat", True)


def test_get_threads_returns_newest_first(consumer_user: User) -> None:
    first = Thread.objects.create(user=consumer_user)
    second = Thread.objects.create(user=consumer_user)

    assert ThreadService().get_threads(consumer_user, limit=10) == [second, first]


def test_get_threads_orders_same_created_at_by_newest_id(consumer_user: User) -> None:
    first = Thread.objects.create(user=consumer_user)
    second = Thread.objects.create(user=consumer_user)
    Thread.objects.update(created_at=first.created_at)

    assert ThreadService().get_threads(consumer_user, limit=10) == [second, first]


def test_get_threads_returns_at_most_limit(consumer_user: User) -> None:
    Thread.objects.create(user=consumer_user)
    second = Thread.objects.create(user=consumer_user)

    assert ThreadService().get_threads(consumer_user, limit=1) == [second]


@pytest.mark.usefixtures("other_thread")
def test_get_threads_skips_other_users_threads(consumer_user: User, thread: Thread) -> None:
    assert ThreadService().get_threads(consumer_user, limit=10) == [thread]


def test_get_threads_skips_deleted_threads(consumer_user: User) -> None:
    Thread.objects.create(user=consumer_user, is_active=False)

    assert ThreadService().get_threads(consumer_user, limit=10) == []


def test_get_threads_after_returns_older_threads(consumer_user: User) -> None:
    first = Thread.objects.create(user=consumer_user)
    second = Thread.objects.create(user=consumer_user)
    third = Thread.objects.create(user=consumer_user)

    threads = ThreadService().get_threads(consumer_user, limit=10, after=third.public_id)

    assert threads == [second, first]


def test_get_threads_after_breaks_created_at_ties_by_id(consumer_user: User) -> None:
    first = Thread.objects.create(user=consumer_user)
    second = Thread.objects.create(user=consumer_user)
    Thread.objects.update(created_at=first.created_at)

    threads = ThreadService().get_threads(consumer_user, limit=10, after=second.public_id)

    assert threads == [first]


def test_get_threads_after_deleted_thread_continues_from_it(consumer_user: User) -> None:
    first = Thread.objects.create(user=consumer_user)
    second = Thread.objects.create(user=consumer_user, is_active=False)

    threads = ThreadService().get_threads(consumer_user, limit=10, after=second.public_id)

    assert threads == [first]


@pytest.mark.usefixtures("thread")
def test_get_threads_after_other_users_thread_returns_nothing(
    consumer_user: User, other_thread: Thread
) -> None:
    threads = ThreadService().get_threads(consumer_user, limit=10, after=other_thread.public_id)

    assert threads == []


@pytest.mark.usefixtures("thread")
def test_get_threads_after_unknown_id_returns_nothing(consumer_user: User) -> None:
    assert ThreadService().get_threads(consumer_user, limit=10, after=uuid4()) == []


@pytest.mark.usefixtures("thread")
def test_get_threads_runs_one_query(
    consumer_user: User, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    with django_assert_num_queries(1):
        ThreadService().get_threads(consumer_user, limit=10)


def test_get_threads_after_runs_one_query(
    consumer_user: User, thread: Thread, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    with django_assert_num_queries(1):
        ThreadService().get_threads(consumer_user, limit=10, after=thread.public_id)


@pytest.mark.usefixtures("thread")
def test_exists_threads_true_when_user_has_one(consumer_user: User) -> None:
    assert ThreadService().exists_threads(consumer_user)


@pytest.mark.usefixtures("other_thread")
def test_exists_threads_false_when_only_others_or_deleted(consumer_user: User) -> None:
    Thread.objects.create(user=consumer_user, is_active=False)

    assert not ThreadService().exists_threads(consumer_user)


def test_get_thread_returns_own_thread(consumer_user: User, thread: Thread) -> None:
    assert ThreadService().get_thread(consumer_user, thread.public_id) == thread


def test_get_thread_returns_none_for_other_users_thread(
    consumer_user: User, other_thread: Thread
) -> None:
    assert ThreadService().get_thread(consumer_user, other_thread.public_id) is None


def test_get_thread_returns_none_for_deleted_thread(consumer_user: User, thread: Thread) -> None:
    Thread.objects.filter(pk=thread.pk).update(is_active=False)

    assert ThreadService().get_thread(consumer_user, thread.public_id) is None


def test_get_thread_returns_none_for_unknown_id(consumer_user: User) -> None:
    assert ThreadService().get_thread(consumer_user, uuid4()) is None


def test_rename_changes_title_and_updated_at(consumer_user: User, thread: Thread) -> None:
    updated_at = thread.updated_at

    renamed = ThreadService().rename(consumer_user, thread.public_id, "Sleep")

    thread.refresh_from_db()
    assert renamed
    assert thread.title == "Sleep"
    assert thread.updated_at > updated_at


def test_rename_refuses_other_users_thread(consumer_user: User, other_thread: Thread) -> None:
    renamed = ThreadService().rename(consumer_user, other_thread.public_id, "Mine now")

    other_thread.refresh_from_db()
    assert not renamed
    assert other_thread.title == "Not yours"


def test_rename_refuses_deleted_thread(consumer_user: User, thread: Thread) -> None:
    Thread.objects.filter(pk=thread.pk).update(is_active=False)

    renamed = ThreadService().rename(consumer_user, thread.public_id, "Sleep")

    thread.refresh_from_db()
    assert not renamed
    assert thread.title == "Exam stress"


def test_rename_fails_when_title_blank(consumer_user: User, thread: Thread) -> None:
    with pytest.raises(IntegrityError, match="threads_title_not_blank"):
        ThreadService().rename(consumer_user, thread.public_id, "   ")


def test_rename_runs_one_query(
    consumer_user: User, thread: Thread, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    with django_assert_num_queries(1):
        ThreadService().rename(consumer_user, thread.public_id, "Sleep")


def test_delete_hides_thread_and_moves_updated_at(consumer_user: User, thread: Thread) -> None:
    updated_at = thread.updated_at

    deleted = ThreadService().delete(consumer_user, thread.public_id)

    thread.refresh_from_db()
    assert deleted
    assert not thread.is_active
    assert thread.updated_at > updated_at


def test_delete_refuses_other_users_thread(consumer_user: User, other_thread: Thread) -> None:
    deleted = ThreadService().delete(consumer_user, other_thread.public_id)

    other_thread.refresh_from_db()
    assert not deleted
    assert other_thread.is_active


def test_delete_refuses_already_deleted_thread(consumer_user: User, thread: Thread) -> None:
    Thread.objects.filter(pk=thread.pk).update(is_active=False)

    assert not ThreadService().delete(consumer_user, thread.public_id)


def test_delete_runs_one_query(
    consumer_user: User, thread: Thread, django_assert_num_queries: DjangoAssertNumQueries
) -> None:
    with django_assert_num_queries(1):
        ThreadService().delete(consumer_user, thread.public_id)
