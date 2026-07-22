from fastapi import APIRouter, Cookie, Request, Response, status

from backend.auth.dependencies import DependsAuthService, RequireRefreshToken
from backend.auth.schemas import (
    LoginOut,
    LoginRequest,
    MessageOut,
    RegisterOut,
    RegisterRequest,
    TokenOut,
    UserOut,
)
from backend.auth.services._helpers import decode_user_id
from backend.config import settings
from backend.limiter import limiter, refresh_token_rate_limit_key

router = APIRouter(prefix="/api/auth", tags=["Auth"])

_COOKIE_OPTS = dict(httponly=True, samesite="lax", secure=False)  # set secure=True behind TLS


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie("refresh_token", refresh_token, **_COOKIE_OPTS)


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
    response_model=RegisterOut,
    responses={
        status.HTTP_409_CONFLICT: {"description": "Email or username already taken"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "Validation error (invalid email, short password, etc.)"
        },
    },
)
@limiter.limit(settings.rate_limit_register)
async def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    auth_service: DependsAuthService,
) -> RegisterOut:
    user = await auth_service.register(
        email=payload.email,
        username=payload.username,
        password=payload.password,
    )
    return RegisterOut(message="account created", user=UserOut.model_validate(user))


@router.post(
    "/login",
    summary="Login — returns access token, sets refresh token cookie",
    response_model=LoginOut,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Invalid credentials"},
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "Account locked after too many failed attempts"
        },
    },
)
@limiter.limit(settings.rate_limit_login)
async def login(
    request: Request,
    payload: LoginRequest,
    auth_service: DependsAuthService,
    response: Response,
) -> LoginOut:
    access_token, refresh_token = await auth_service.login(payload.email, payload.password)
    _set_refresh_cookie(response, refresh_token)
    user_id = decode_user_id(request, access_token)
    user = await auth_service.get_current_user(user_id)
    return LoginOut(
        message="logged in",
        access_token=access_token,
        refresh_token=refresh_token,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/refresh",
    summary="Rotate tokens — returns new access and refresh tokens",
    response_model=TokenOut,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid refresh token"},
    },
)
@limiter.limit(settings.rate_limit_refresh, key_func=refresh_token_rate_limit_key)
async def refresh(
    request: Request,
    auth_service: DependsAuthService,
    response: Response,
    token: RequireRefreshToken,
) -> TokenOut:
    access_token, new_refresh_token = await auth_service.refresh(token)
    _set_refresh_cookie(response, new_refresh_token)
    user_id = decode_user_id(request, access_token)
    user = await auth_service.get_current_user(user_id)
    return TokenOut(
        message="tokens refreshed",
        access_token=access_token,
        refresh_token=new_refresh_token,
        user=UserOut.model_validate(user),
    )


@router.post(
    "/logout",
    summary="Invalidate refresh token and clear cookie",
    response_model=MessageOut,
)
async def logout(
    auth_service: DependsAuthService,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
) -> MessageOut:
    if refresh_token:
        await auth_service.logout(refresh_token)
    response.delete_cookie("refresh_token")
    return MessageOut(message="logged out")
