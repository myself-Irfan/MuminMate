from uuid import uuid4

from django.conf import settings
from django.db import models

from core.models import TimestampedAbstract


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
