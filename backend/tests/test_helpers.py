import jwt
import pytest
from argon2 import PasswordHasher

from backend.auth.services._helpers import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    password_needs_rehash,
    verify_password,
)
from backend.config import settings


def test_hash_password_returns_argon2_hash():
    h = hash_password("mypassword")
    assert h.startswith("$argon2")


def test_verify_password_correct():
    h = hash_password("correct")
    assert verify_password("correct", h)


def test_verify_password_wrong():
    h = hash_password("correct")
    assert not verify_password("wrong", h)


def test_password_needs_rehash_with_old_params():
    # Hash with weaker params to simulate a hash made with old settings
    old_hasher = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1)
    old_hash = old_hasher.hash("password123")
    assert verify_password("password123", old_hash)
    assert password_needs_rehash(old_hash)


def test_password_needs_rehash_current_params():
    h = hash_password("password123")
    assert not password_needs_rehash(h)


def test_hash_token_is_deterministic():
    assert hash_token("abc") == hash_token("abc")


def test_hash_token_different_inputs():
    assert hash_token("abc") != hash_token("xyz")


def test_hash_token_is_hex_string():
    result = hash_token("test")
    assert len(result) == 64
    int(result, 16)  # raises ValueError if not valid hex


def test_create_access_token_contains_user_id():
    token = create_access_token(42)
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert payload["sub"] == "42"


def test_create_access_token_has_expiry():
    token = create_access_token(1)
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert "exp" in payload


def test_create_access_token_different_users():
    t1 = create_access_token(1)
    t2 = create_access_token(2)
    assert t1 != t2


def test_create_refresh_token_returns_pair():
    raw, hashed = create_refresh_token()
    assert raw != hashed


def test_create_refresh_token_hash_matches_raw():
    raw, hashed = create_refresh_token()
    assert hash_token(raw) == hashed


def test_create_refresh_token_is_unique():
    _, h1 = create_refresh_token()
    _, h2 = create_refresh_token()
    assert h1 != h2


@pytest.mark.parametrize("user_id", [1, 999, 2**31 - 1])
def test_create_access_token_various_ids(user_id: int):
    token = create_access_token(user_id)
    payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    assert payload["sub"] == str(user_id)
