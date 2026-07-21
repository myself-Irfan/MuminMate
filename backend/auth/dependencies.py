from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from backend.auth.entities import User
from backend.auth.repository import SQLAlchemyUserRepository
from backend.auth.schemas import RefreshRequest
from backend.auth.services.auth_service import AuthService
from backend.database import DbSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _get_repo(db: DbSession) -> SQLAlchemyUserRepository:
    return SQLAlchemyUserRepository(db)


def _get_auth_service(
    repo: Annotated[SQLAlchemyUserRepository, Depends(_get_repo)],
) -> AuthService:
    return AuthService(repo)


DependsAuthService = Annotated[AuthService, Depends(_get_auth_service)]


async def _get_current_user(
    request: Request,
    auth_service: DependsAuthService,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    return await auth_service.get_current_user(request, token)


CurrentUser = Annotated[User, Depends(_get_current_user)]


async def _require_refresh_token(
    request: Request,
    body: RefreshRequest = RefreshRequest(),
    cookie_token: str | None = Cookie(alias="refresh_token", default=None),
) -> str:
    """Resolve the refresh token from body or cookie, 401 if neither is present.

    Runs as a FastAPI dependency, so it's resolved before slowapi's key_func —
    this guarantees `/refresh`'s rate limiter never sees a request without a
    token, so its key_func never needs to fall back to IP.
    """
    token = body.refresh_token or cookie_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing refresh token"
        )
    request.state.refresh_token = token
    return token


RequireRefreshToken = Annotated[str, Depends(_require_refresh_token)]
