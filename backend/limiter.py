from fastapi import status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request


def user_rate_limit_key(request: Request) -> str:
    return f"user:{request.state.jwt_user_id}"


def refresh_user_rate_limit_key(request: Request) -> str:
    user_id = getattr(request.state, "refresh_user_id", None)
    return f"user:{user_id}" if user_id is not None else ""


limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": str(exc.detail)}
    )
    return limiter._inject_headers(response, request.state.view_rate_limit)
