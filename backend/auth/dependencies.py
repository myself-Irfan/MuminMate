from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from backend.auth.entities import User
from backend.auth.repository import SQLAlchemyUserRepository
from backend.auth.schemas import RefreshRequest
from backend.auth.services._helpers import decode_user_id
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
    user_id = decode_user_id(request, token)
    return await auth_service.get_current_user(user_id)


CurrentUser = Annotated[User, Depends(_get_current_user)]


async def _require_refresh_token(
    request: Request,
    auth_service: DependsAuthService,
    body: RefreshRequest = RefreshRequest(),
    cookie_token: str | None = Cookie(alias="refresh_token", default=None),
) -> str:
    token = body.refresh_token or cookie_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing refresh token"
        )
    request.state.refresh_user_id = await auth_service.get_refresh_token_owner(token)
    return token


RequireRefreshToken = Annotated[str, Depends(_require_refresh_token)]
