from abc import ABC, abstractmethod
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.entities import LoginAttempt, RefreshToken, User


class UserRepository(ABC):
    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    async def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    async def create(self, email: str, username: str, password_hash: str) -> User: ...

    @abstractmethod
    async def save_refresh_token(
        self, user_id: int, token_hash: str, expires_at: datetime
    ) -> None: ...

    @abstractmethod
    async def get_refresh_token(self, token_hash: str) -> RefreshToken | None: ...

    @abstractmethod
    async def delete_refresh_token(self, token_hash: str) -> bool: ...

    @abstractmethod
    async def count_failed_attempts(self, email: str, since: datetime) -> int: ...

    @abstractmethod
    async def record_attempt(self, email: str, succeeded: bool) -> None: ...

    @abstractmethod
    async def clear_failed_attempts(self, email: str) -> None: ...

    @abstractmethod
    async def update_password_hash(self, user_id: int, password_hash: str) -> None: ...

    @abstractmethod
    async def rotate_refresh_token(
        self, old_hash: str, user_id: int, new_hash: str, expires_at: datetime
    ) -> bool: ...


class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_email(self, email: str) -> User | None:
        result = await self._db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self._db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create(self, email: str, username: str, password_hash: str) -> User:
        user = User(email=email, username=username, password_hash=password_hash)
        self._db.add(user)
        await self._db.commit()
        await self._db.refresh(user)
        return user

    async def save_refresh_token(self, user_id: int, token_hash: str, expires_at: datetime) -> None:
        token = RefreshToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
        self._db.add(token)
        await self._db.commit()

    async def get_refresh_token(self, token_hash: str) -> RefreshToken | None:
        result = await self._db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        return result.scalar_one_or_none()

    async def delete_refresh_token(self, token_hash: str) -> bool:
        result = await self._db.execute(
            delete(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        await self._db.commit()
        return result.rowcount > 0

    async def count_failed_attempts(self, email: str, since: datetime) -> int:
        result = await self._db.execute(
            select(func.count()).where(
                LoginAttempt.email == email,
                LoginAttempt.succeeded == False,  # noqa: E712
                LoginAttempt.attempted_at >= since,
            )
        )
        return result.scalar_one()

    async def record_attempt(self, email: str, succeeded: bool) -> None:
        self._db.add(LoginAttempt(email=email, succeeded=succeeded))
        await self._db.commit()

    async def clear_failed_attempts(self, email: str) -> None:
        await self._db.execute(
            delete(LoginAttempt).where(
                LoginAttempt.email == email,
                LoginAttempt.succeeded == False,  # noqa: E712
            )
        )
        await self._db.commit()

    async def update_password_hash(self, user_id: int, password_hash: str) -> None:
        user = await self.get_by_id(user_id)
        if user:
            user.password_hash = password_hash
            await self._db.commit()

    async def rotate_refresh_token(
        self, old_hash: str, user_id: int, new_hash: str, expires_at: datetime
    ) -> bool:
        result = await self._db.execute(
            delete(RefreshToken).where(RefreshToken.token_hash == old_hash)
        )
        if result.rowcount == 0:
            await self._db.rollback()
            return False
        self._db.add(RefreshToken(user_id=user_id, token_hash=new_hash, expires_at=expires_at))
        await self._db.commit()
        return True
