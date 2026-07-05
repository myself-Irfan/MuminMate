from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.threads.entities import Thread


class ThreadRepository(ABC):
    @abstractmethod
    async def list_for_user(self, user_id: int) -> list[Thread]: ...

    @abstractmethod
    async def get_by_id(self, thread_id: int) -> Thread | None: ...

    @abstractmethod
    async def create(self, user_id: int, title: str, expires_at: datetime) -> Thread: ...

    @abstractmethod
    async def rename(self, thread_id: int, title: str) -> None: ...

    @abstractmethod
    async def delete(self, thread_id: int) -> bool: ...


class SQLAlchemyThreadRepository(ThreadRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def list_for_user(self, user_id: int) -> list[Thread]:
        result = await self._db.execute(
            select(Thread).where(Thread.user_id == user_id).order_by(Thread.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_id(self, thread_id: int) -> Thread | None:
        result = await self._db.execute(select(Thread).where(Thread.id == thread_id))
        return result.scalar_one_or_none()

    async def create(self, user_id: int, title: str, expires_at: datetime) -> Thread:
        thread = Thread(user_id=user_id, title=title, expires_at=expires_at)
        self._db.add(thread)
        await self._db.commit()
        await self._db.refresh(thread)
        return thread

    async def rename(self, thread_id: int, title: str) -> None:
        thread = await self.get_by_id(thread_id)
        if thread:
            thread.title = title
            await self._db.commit()

    async def delete(self, thread_id: int) -> bool:
        result = await self._db.execute(delete(Thread).where(Thread.id == thread_id))
        await self._db.commit()
        return result.rowcount > 0
