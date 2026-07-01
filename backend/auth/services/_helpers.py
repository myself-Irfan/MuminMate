import hashlib
import uuid
from datetime import datetime, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from backend.config import settings

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
