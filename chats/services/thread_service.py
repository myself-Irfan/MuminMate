from uuid import UUID

from django.db.models import Max, QuerySet, Subquery
from django.utils import timezone

from chats.models import Thread
from users.models import User


class ThreadService:
    def create(self, user: User, title: str) -> Thread:
        return Thread.objects.create(user=user, title=title)

    # Latest message first, computed not stored; `after` is the last thread shown, even if deleted.
    def get_threads(self, user: User, limit: int, after: UUID | None = None) -> list[Thread]:
        threads = self._live_threads(user).annotate(last_message_id=self._last_message_id())
        if after is not None:
            cursor = Thread.objects.filter(user=user, public_id=after).annotate(
                last_message_id=self._last_message_id()
            )
            threads = threads.filter(last_message_id__lt=Subquery(cursor.values("last_message_id")))
        return list(threads.order_by("-last_message_id")[:limit])

    def exists_threads(self, user: User) -> bool:
        return self._live_threads(user).exists()

    def get_thread(self, user: User, public_id: UUID) -> Thread | None:
        try:
            return self._live_threads(user).get(public_id=public_id)
        except Thread.DoesNotExist:
            return None

    # Conditional update, like mark_verified: one query, no check-then-act.
    def rename(self, user: User, public_id: UUID, title: str) -> bool:
        return bool(
            self._live_threads(user)
            .filter(public_id=public_id)
            .update(title=title, updated_at=timezone.now())
        )

    def delete(self, user: User, public_id: UUID) -> bool:
        return bool(
            self._live_threads(user)
            .filter(public_id=public_id)
            .update(is_active=False, updated_at=timezone.now())
        )

    def _live_threads(self, user: User) -> QuerySet[Thread]:
        return Thread.objects.filter(user=user, is_active=True)

    def _last_message_id(self) -> Max:
        return Max("messages__id")
