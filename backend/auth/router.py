from fastapi import APIRouter, Cookie, HTTPException, Request, Response, status

from backend.auth.dependencies import CurrentUser, DependsAuthService
from backend.auth.exceptions import AccountLockedException, AuthException
from backend.auth.schemas import (
    LoginOut,
    LoginRequest,
    MessageOut,
    RefreshRequest,
    RegisterOut,
    RegisterRequest,
    TokenOut,
    UserOut,
)
from backend.limiter import limiter

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
@limiter.limit("5/minute")
async def register(
    request: Request,
    payload: RegisterRequest,
    auth_service: DependsAuthService,
) -> RegisterOut:
    try:
        user = await auth_service.register(
            email=payload.email,
            username=payload.username,
            password=payload.password,
        )
        return RegisterOut(message="account created", user=UserOut.model_validate(user))
    except AuthException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


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
@limiter.limit("10/15minutes")
async def login(
    request: Request,
    payload: LoginRequest,
    auth_service: DependsAuthService,
    response: Response,
) -> LoginOut:
    try:
        access_token, refresh_token = await auth_service.login(payload.email, payload.password)
        _set_refresh_cookie(response, refresh_token)
        user = await auth_service.get_current_user(request, access_token)
        return LoginOut(
            message="logged in",
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserOut.model_validate(user),
        )
    except AccountLockedException as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.message,
            headers={"Retry-After": str(exc.retry_after_minutes * 60)},
        )
    except AuthException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


@router.post(
    "/refresh",
    summary="Rotate tokens — returns new access and refresh tokens",
    response_model=TokenOut,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid refresh token"},
    },
)
@limiter.limit("20/minute")
async def refresh(
    request: Request,
    auth_service: DependsAuthService,
    response: Response,
    body: RefreshRequest = RefreshRequest(),
    cookie_token: str | None = Cookie(alias="refresh_token", default=None),
) -> TokenOut:
    token = body.refresh_token or cookie_token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing refresh token"
        )
    try:
        access_token, new_refresh_token = await auth_service.refresh(token)
        _set_refresh_cookie(response, new_refresh_token)
        return TokenOut(
            message="tokens refreshed", access_token=access_token, refresh_token=new_refresh_token
        )
    except AuthException as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message)


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


@router.get(
    "/me",
    summary="Get current authenticated user",
    response_model=UserOut,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "Missing or invalid access token"},
    },
)
async def me(current_user: CurrentUser) -> UserOut:
    return UserOut.model_validate(current_user)
