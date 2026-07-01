from datetime import datetime, timezone

from backend.auth.entities import User
from backend.auth.exceptions import AccountLockedException, InvalidCredentialsException
from backend.auth.repository import UserRepository
from backend.auth.services._helpers import (
    create_access_token,
    create_refresh_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from backend.config import settings
from backend.logger import get_logger

logger = get_logger(__name__)


class _LoginFlow:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, email: str, password: str) -> tuple[str, str]:
        user = await self._fetch_user(email)
        await self._check_lockout(email)
        await self._verify_credentials(user, password)

        if password_needs_rehash(user.password_hash):
            await self._repo.update_password_hash(user.id, hash_password(password))
            logger.info("password rehashed", user_id=str(user.id))

        return await self._issue_tokens(user)

    async def _fetch_user(self, email: str) -> User:
        user = await self._repo.get_by_email(email)
        if not user:
            logger.warning("login failed", email=email)
            raise InvalidCredentialsException()
        return user

    async def _check_lockout(self, email: str) -> None:
        failures = await self._repo.count_failed_attempts(
            email, since=(datetime.now(timezone.utc) - settings.login_attempt_window)
        )
        if failures >= settings.login_attempt_max_failures:
            logger.warning("login locked", email=email, failures=failures)
            raise AccountLockedException(retry_after_minutes=settings.login_attempt_window_minutes)

    async def _verify_credentials(self, user: User, password: str) -> None:
        if not verify_password(password, user.password_hash):
            await self._repo.record_attempt(email=user.email, succeeded=False)
            logger.warning("login failed", email=user.email)
            raise InvalidCredentialsException()

        await self._repo.record_attempt(email=user.email, succeeded=True)
        await self._repo.clear_failed_attempts(user.email)
        logger.info("credentials verified", email=user.email, user_id=str(user.id))

    async def _issue_tokens(self, user: User) -> tuple[str, str]:
        access_token = create_access_token(user.id)
        refresh_token, token_hash = create_refresh_token()

        await self._repo.save_refresh_token(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=(datetime.now(timezone.utc) + settings.refresh_token_expire),
        )
        return access_token, refresh_token
