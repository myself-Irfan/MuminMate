from typing import Annotated

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer

from backend.auth.entities import User
from backend.auth.repository import SQLAlchemyUserRepository
from backend.auth.services import AuthService
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
    auth_service: DependsAuthService,
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    return await auth_service.get_current_user(token)


CurrentUser = Annotated[User, Depends(_get_current_user)]
