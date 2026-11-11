from uuid import uuid4

from django.conf import settings
from django.db import models

from chats.enums import MessageRole
from core.models import CreatedAtAbstract, TimestampedAbstract


class Thread(TimestampedAbstract):
    title = models.CharField(max_length=200, default="New chat")
    is_active = models.BooleanField(default=True)
    public_id = models.UUIDField(default=uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    class Meta:
        db_table = "threads"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(title__regex=r"\S"),
                name="threads_title_not_blank",
                violation_error_message="Enter a title.",
            ),
        )

    def __str__(self) -> str:
        return self.title


class Message(CreatedAtAbstract):
    role = models.CharField(max_length=16, choices=MessageRole)
    content = models.TextField()
    thread = models.ForeignKey(Thread, on_delete=models.CASCADE, related_name="messages")

    class Meta:
        db_table = "messages"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(role__in=MessageRole.values),
                name="messages_role_valid",
                violation_error_message="Unknown message role.",
            ),
            models.CheckConstraint(
                condition=models.Q(content__regex=r"\S"),
                name="messages_content_not_blank",
                violation_error_message="Write a message.",
            ),
        )

    # Content stays out: this string can reach logs and the admin.
    def __str__(self) -> str:
        return f"{self.get_role_display()} message {self.pk}"
