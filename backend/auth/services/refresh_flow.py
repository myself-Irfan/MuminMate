from datetime import datetime, timezone

from backend.auth.entities import RefreshToken
from backend.auth.exceptions import InvalidTokenException
from backend.auth.repository import UserRepository
from backend.auth.services._helpers import create_access_token, create_refresh_token
from backend.config import settings


class _RefreshFlow:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def execute(self, token_hash: str) -> tuple[str, str]:
        existing = await self._fetch_refresh_token(token_hash)
        return await self._rotate_tokens(existing, token_hash)

    async def _fetch_refresh_token(self, token_hash: str) -> RefreshToken:
        existing = await self._repo.get_refresh_token(token_hash)
        if not existing or existing.expires_at < datetime.now(timezone.utc):
            raise InvalidTokenException()
        return existing

    async def _rotate_tokens(self, existing: RefreshToken, old_hash: str) -> tuple[str, str]:
        new_access_token = create_access_token(existing.user_id)
        new_refresh_token, new_token_hash = create_refresh_token()
        new_expires_at = datetime.now(timezone.utc) + settings.refresh_token_expire

        rotated = await self._repo.rotate_refresh_token(
            old_hash=old_hash,
            user_id=existing.user_id,
            new_hash=new_token_hash,
            expires_at=new_expires_at,
        )
        if not rotated:
            raise InvalidTokenException()

        return new_access_token, new_refresh_token
