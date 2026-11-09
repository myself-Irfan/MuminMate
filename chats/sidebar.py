from dataclasses import dataclass
from uuid import UUID

from django.conf import settings

from chats.models import Thread
from chats.services.thread_service import ThreadService
from users.models import User


@dataclass(frozen=True)
class Sidebar:
    threads: list[Thread]
    next_after: UUID | None
    open_id: UUID | None


# One extra row tells whether a "Show more" link is needed, without a count query.
def get_sidebar(user: User, after: UUID | None, open_id: UUID | None) -> Sidebar:
    size = settings.THREAD_LIST_PAGE_SIZE
    threads = ThreadService().get_threads(user, limit=size + 1, after=after)
    next_after = threads[size - 1].public_id if len(threads) > size else None
    return Sidebar(threads[:size], next_after, open_id)
