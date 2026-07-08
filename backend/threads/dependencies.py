from typing import Annotated

from fastapi import Depends

from backend.database import DbSession
from backend.threads.repository import SQLAlchemyThreadRepository
from backend.threads.service import ThreadService


def _get_repo(db: DbSession) -> SQLAlchemyThreadRepository:
    return SQLAlchemyThreadRepository(db)


def _get_thread_service(
    repo: Annotated[SQLAlchemyThreadRepository, Depends(_get_repo)],
) -> ThreadService:
    return ThreadService(repo)


DependsThreadService = Annotated[ThreadService, Depends(_get_thread_service)]
