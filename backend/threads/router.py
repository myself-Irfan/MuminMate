from fastapi import APIRouter, HTTPException, Request, Response, status

from backend.auth.dependencies import CurrentUser
from backend.auth.schemas import MessageOut
from backend.config import settings
from backend.limiter import limiter
from backend.threads.dependencies import DependsThreadService
from backend.threads.exceptions import ThreadException
from backend.threads.schemas import CreateThreadRequest, RenameThreadRequest, ThreadOut

router = APIRouter(prefix="/api/threads", tags=["Threads"])

_OWNERSHIP_RESPONSES = {
    status.HTTP_404_NOT_FOUND: {"description": "Thread not found"},
    status.HTTP_403_FORBIDDEN: {"description": "Thread belongs to another user"},
}


@router.get(
    "",
    summary="List the current user's threads",
    response_model=list[ThreadOut],
)
async def list_threads(
    current_user: CurrentUser,
    thread_service: DependsThreadService,
) -> list[ThreadOut]:
    threads = await thread_service.list_for_user(current_user.id)
    return [ThreadOut.model_validate(thread) for thread in threads]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new thread",
    response_model=ThreadOut,
)
@limiter.limit(settings.rate_limit_threads_create)
async def create_thread(
    request: Request,
    response: Response,
    payload: CreateThreadRequest,
    current_user: CurrentUser,
    thread_service: DependsThreadService,
) -> ThreadOut:
    thread = await thread_service.create(current_user.id, payload.title)
    return ThreadOut.model_validate(thread)


@router.get(
    "/{thread_id}",
    summary="Get a single thread",
    response_model=ThreadOut,
    responses=_OWNERSHIP_RESPONSES,
)
async def get_thread(
    thread_id: int,
    current_user: CurrentUser,
    thread_service: DependsThreadService,
) -> ThreadOut:
    try:
        thread = await thread_service.get_owned(thread_id, current_user.id)
    except ThreadException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return ThreadOut.model_validate(thread)


@router.patch(
    "/{thread_id}",
    summary="Rename a thread",
    response_model=ThreadOut,
    responses=_OWNERSHIP_RESPONSES,
)
async def rename_thread(
    thread_id: int,
    payload: RenameThreadRequest,
    current_user: CurrentUser,
    thread_service: DependsThreadService,
) -> ThreadOut:
    try:
        thread = await thread_service.rename(thread_id, current_user.id, payload.title)
    except ThreadException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return ThreadOut.model_validate(thread)


@router.delete(
    "/{thread_id}",
    summary="Delete a thread",
    response_model=MessageOut,
    responses=_OWNERSHIP_RESPONSES,
)
@limiter.limit(settings.rate_limit_threads_delete)
async def delete_thread(
    request: Request,
    response: Response,
    thread_id: int,
    current_user: CurrentUser,
    thread_service: DependsThreadService,
) -> MessageOut:
    try:
        await thread_service.delete(thread_id, current_user.id)
    except ThreadException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return MessageOut(message="thread deleted")
