from unittest.mock import Mock

import pytest
from django.db import IntegrityError

from chats.enums import MessageRole
from chats.models import Message, Thread
from chats.services.message_service import MessageService
from users.models import User


def test_start_creates_titled_thread_with_the_message(consumer_user: User) -> None:
    thread = MessageService().start(consumer_user, "Exam stress tonight")

    assert (thread.user, thread.title) == (consumer_user, "Exam stress tonight")
    assert list(thread.messages.values_list("role", "content")) == [
        (MessageRole.USER, "Exam stress tonight")
    ]


def test_start_saves_no_thread_when_message_save_fails(
    consumer_user: User, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "chats.services.message_service.Message.objects.create",
        Mock(side_effect=IntegrityError("refused")),
    )

    with pytest.raises(IntegrityError):
        MessageService().start(consumer_user, "Exam stress")

    assert not Thread.objects.exists()


def test_send_saves_user_message_in_thread(thread: Thread) -> None:
    message = MessageService().send(thread, "Still anxious")

    assert message == thread.messages.get()
    assert (message.role, message.content) == (MessageRole.USER, "Still anxious")


def test_send_keeps_title(thread: Thread) -> None:
    MessageService().send(thread, "Still anxious")

    thread.refresh_from_db()
    assert thread.title == "Exam stress"


def test_reply_echoes_latest_user_message(thread: Thread) -> None:
    Message.objects.create(thread=thread, role=MessageRole.USER, content="First")
    Message.objects.create(thread=thread, role=MessageRole.ASSISTANT, content="You said: First")
    Message.objects.create(thread=thread, role=MessageRole.USER, content="Second")

    reply = MessageService().reply(thread)

    assert (reply.thread, reply.role, reply.content) == (
        thread,
        MessageRole.ASSISTANT,
        "You said: Second",
    )


def test_get_messages_returns_thread_messages_in_order(
    thread: Thread, other_thread: Thread
) -> None:
    first = Message.objects.create(thread=thread, role=MessageRole.USER, content="First")
    Message.objects.create(thread=other_thread, role=MessageRole.USER, content="Not here")
    second = Message.objects.create(thread=thread, role=MessageRole.ASSISTANT, content="Second")

    assert MessageService().get_messages(thread) == [first, second]
