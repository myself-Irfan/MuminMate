from starlette.requests import Request

from backend.auth.entities import User
from backend.auth.exceptions import InvalidTokenException, UserAlreadyExistsException
from backend.auth.repository import UserRepository
from backend.auth.services._helpers import decode_user_id, hash_password, hash_token
from backend.auth.services.login_flow import _LoginFlow
from backend.auth.services.refresh_flow import _RefreshFlow
from backend.logger import get_logger

logger = get_logger(__name__)


class AuthService:
    def __init__(self, repo: UserRepository) -> None:
        self._repo = repo

    async def register(self, email: str, username: str, password: str) -> User:
        if await self._repo.get_by_email(email):
            raise UserAlreadyExistsException("email")
        user = await self._repo.create(
            email=email, username=username, password_hash=hash_password(password)
        )
        logger.info("user registered", email=email, user_id=str(user.id))
        return user

    async def login(self, email: str, password: str) -> tuple[str, str]:
        return await _LoginFlow(self._repo).execute(email, password)

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        token_hash = hash_token(refresh_token)
        return await _RefreshFlow(self._repo).execute(token_hash)

    async def logout(self, refresh_token: str) -> None:
        await self._repo.delete_refresh_token(hash_token(refresh_token))

    async def get_current_user(self, request: Request, token: str) -> User:
        user_id = decode_user_id(request, token)
        if user_id is None:
            raise InvalidTokenException()

        user = await self._repo.get_by_id(user_id)
        if not user:
            raise InvalidTokenException()
        return user
