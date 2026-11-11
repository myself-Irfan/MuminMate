import pytest
from django.core.exceptions import ValidationError
from django.db import DataError, IntegrityError
from django.utils import timezone

from chats.enums import MessageRole
from chats.models import Message, Thread
from users.models import User


def test_str_returns_title() -> None:
    thread = Thread(title="Exam stress")

    assert str(thread) == "Exam stress"


def test_new_thread_is_active_with_default_title(consumer_user: User) -> None:
    thread = Thread.objects.create(user=consumer_user)

    assert (thread.title, thread.is_active) == ("New chat", True)


def test_new_threads_get_different_random_public_ids(consumer_user: User) -> None:
    first = Thread.objects.create(user=consumer_user)
    second = Thread.objects.create(user=consumer_user)

    assert first.public_id != second.public_id
    assert (first.public_id.version, second.public_id.version) == (4, 4)


def test_save_fails_when_public_id_taken(consumer_user: User) -> None:
    taken = Thread.objects.create(user=consumer_user)

    with pytest.raises(IntegrityError, match="public_id"):
        Thread.objects.create(user=consumer_user, public_id=taken.public_id)


@pytest.mark.parametrize("title", ["", "   "])
def test_save_fails_when_title_blank(consumer_user: User, title: str) -> None:
    thread = Thread(user=consumer_user, title=title)

    with pytest.raises(IntegrityError, match="threads_title_not_blank"):
        thread.save()


def test_validate_constraints_fails_when_title_blank(consumer_user: User) -> None:
    thread = Thread(user=consumer_user, title=" ")

    with pytest.raises(ValidationError, match="Enter a title"):
        thread.validate_constraints()


def test_save_fails_when_title_longer_than_200(consumer_user: User) -> None:
    thread = Thread(user=consumer_user, title="a" * 201)

    with pytest.raises(DataError, match="value too long"):
        thread.save()


def test_created_at_set_on_create(consumer_user: User) -> None:
    before = timezone.now()

    thread = Thread.objects.create(user=consumer_user)

    assert before <= thread.created_at <= timezone.now()


def test_save_moves_updated_at_and_keeps_created_at(consumer_user: User) -> None:
    thread = Thread.objects.create(user=consumer_user)
    created_at, updated_at = thread.created_at, thread.updated_at

    thread.title = "Exam stress"
    thread.save()

    thread.refresh_from_db()
    assert thread.created_at == created_at
    assert thread.updated_at > updated_at


def test_deleting_user_deletes_their_threads(consumer_user: User) -> None:
    Thread.objects.create(user=consumer_user)

    consumer_user.delete()

    assert not Thread.objects.exists()


def test_message_str_names_role_not_content(thread: Thread) -> None:
    message = Message.objects.create(thread=thread, role=MessageRole.USER, content="Private")

    assert str(message) == f"User message {message.pk}"


def test_message_save_fails_when_role_unknown(thread: Thread) -> None:
    message = Message(thread=thread, role="system", content="Hi")

    with pytest.raises(IntegrityError, match="messages_role_valid"):
        message.save()


@pytest.mark.parametrize("content", ["", " \n "])
def test_message_save_fails_when_content_blank(thread: Thread, content: str) -> None:
    message = Message(thread=thread, role=MessageRole.USER, content=content)

    with pytest.raises(IntegrityError, match="messages_content_not_blank"):
        message.save()


def test_deleting_thread_deletes_its_messages(thread: Thread) -> None:
    Message.objects.create(thread=thread, role=MessageRole.USER, content="Hi")

    thread.delete()

    assert not Message.objects.exists()
