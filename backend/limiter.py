from fastapi import status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request

from backend.auth.services._helpers import hash_token


def user_rate_limit_key(request: Request) -> str:
    """Key by user_id, for routes behind the `CurrentUser` dependency.

    FastAPI resolves `CurrentUser` (401s on a missing/invalid token) before
    slowapi's key_func ever runs, and that dependency already calls
    decode_user_id, caching the result on request.state.jwt_user_id. So this
    always finds a valid cached user_id — no IP fallback, ever: reaching this
    without one would mean CurrentUser already let something broken through.
    """
    return f"user:{request.state.jwt_user_id}"


def refresh_token_rate_limit_key(request: Request) -> str:
    """Key by the refresh token's hash — /refresh and /logout only carry that
    opaque token, not a JWT, so there's no user_id to decode without a DB hit.

    No IP fallback: /refresh requires a token via `require_refresh_token`
    before this ever runs (stashed on `request.state.refresh_token`), so it's
    always present there. /logout has no such requirement — a missing cookie
    is a legitimate no-op, so this returns "" for that case, which slowapi
    treats as "skip this limit" rather than bucketing by IP. Falling back to
    IP would let one caller's abuse throttle unrelated users behind the same
    address, which is exactly what keying by identity is meant to avoid.
    """
    token = getattr(request.state, "refresh_token", None) or request.cookies.get("refresh_token")
    if token:
        return f"reftok:{hash_token(token)}"
    return ""


limiter = Limiter(
    key_func=get_remote_address,
    headers_enabled=True,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    response = JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS, content={"detail": str(exc.detail)}
    )
    return limiter._inject_headers(response, request.state.view_rate_limit)
