from django.db import transaction

from chats.enums import MessageRole
from chats.models import Message, Thread
from chats.services.thread_service import ThreadService
from chats.titles import make_title
from users.models import User


# Saving a message and making its reply are separate steps: the AI's wait holds no transaction.
class MessageService:
    # The chat and its first message are saved together: no chat is ever empty.
    def start(self, user: User, content: str) -> Thread:
        with transaction.atomic():
            thread = ThreadService().create(user, make_title(content))
            Message.objects.create(thread=thread, role=MessageRole.USER, content=content)
        return thread

    def send(self, thread: Thread, content: str) -> Message:
        return Message.objects.create(thread=thread, role=MessageRole.USER, content=content)

    # An echo until the AI arrives in phase 3.
    def reply(self, thread: Thread) -> Message:
        latest = (
            thread.messages.filter(role=MessageRole.USER)
            .order_by("-id")
            .values_list("content", flat=True)
            .first()
        )
        return Message.objects.create(
            thread=thread, role=MessageRole.ASSISTANT, content=f"You said: {latest}"
        )

    def get_messages(self, thread: Thread) -> list[Message]:
        return list(thread.messages.order_by("id"))
