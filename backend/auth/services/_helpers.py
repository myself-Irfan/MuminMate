import hashlib
import uuid
from datetime import datetime, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from starlette.requests import Request

from backend.config import settings

_UNSET = object()

_pwd_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    return _pwd_hasher.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        _pwd_hasher.verify(hashed, plain)
        return True
    except VerifyMismatchError:
        return False


def password_needs_rehash(hashed: str) -> bool:
    return _pwd_hasher.check_needs_rehash(hashed)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + settings.access_token_expire
    return jwt.encode(
        {"sub": str(user_id), "exp": expire}, settings.secret_key, algorithm=settings.algorithm
    )


def create_refresh_token() -> tuple[str, str]:
    raw = str(uuid.uuid4())
    return raw, hash_token(raw)


def _decode_jwt_sub(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        return int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        return None


def decode_user_id(request: Request, token: str) -> int | None:
    """Decode the access token's user id once per request, caching on request.state.

    Middleware, auth, and rate limiting all need this same value from the same
    token within a single request — decoding once avoids redundant jwt.decode calls.
    """
    cached = getattr(request.state, "jwt_user_id", _UNSET)
    if cached is not _UNSET:
        return cached
    user_id = _decode_jwt_sub(token)
    request.state.jwt_user_id = user_id
    return user_id
