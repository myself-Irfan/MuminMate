from datetime import datetime, timezone

from backend.config import settings
from backend.logger import get_logger
from backend.threads.entities import Thread
from backend.threads.exceptions import ThreadNotFoundException, ThreadNotOwnedException
from backend.threads.repository import ThreadRepository

logger = get_logger(__name__)

_DEFAULT_TITLE = "New thread"


class ThreadService:
    def __init__(self, repo: ThreadRepository) -> None:
        self._repo = repo

    async def list_for_user(self, user_id: int) -> list[Thread]:
        return await self._repo.list_for_user(user_id)

    async def create(self, user_id: int, title: str | None) -> Thread:
        thread = await self._repo.create(
            user_id=user_id,
            title=title or _DEFAULT_TITLE,
            expires_at=datetime.now(timezone.utc) + settings.thread_expiry,
        )
        logger.info("thread created", thread_id=str(thread.id), user_id=str(user_id))
        return thread

    async def get_owned(self, thread_id: int, user_id: int) -> Thread:
        thread = await self._repo.get_by_id(thread_id)

        if not thread:
            raise ThreadNotFoundException()

        if thread.user_id != user_id:
            raise ThreadNotOwnedException()

        return thread

    async def rename(self, thread_id: int, user_id: int, title: str) -> Thread:
        thread = await self.get_owned(thread_id, user_id)
        await self._repo.rename(thread_id, title)
        thread.title = title
        return thread

    async def delete(self, thread_id: int, user_id: int) -> None:
        await self.get_owned(thread_id, user_id)
        await self._repo.delete(thread_id)
