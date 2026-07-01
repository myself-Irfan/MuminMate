import pytest
from pydantic import ValidationError

from backend.auth.schemas import RegisterRequest


def test_valid_register_request():
    r = RegisterRequest(email="user@example.com", username="validuser", password="password123")
    assert r.email == "user@example.com"
    assert r.username == "validuser"


def test_username_whitespace_stripped():
    r = RegisterRequest(email="user@example.com", username="  alice  ", password="password123")
    assert r.username == "alice"


def test_username_too_short():
    with pytest.raises(ValidationError, match="at least 3 characters"):
        RegisterRequest(email="u@example.com", username="ab", password="password123")


def test_username_too_short_after_strip():
    with pytest.raises(ValidationError, match="at least 3 characters"):
        RegisterRequest(email="u@example.com", username="  a  ", password="password123")


def test_username_too_long():
    with pytest.raises(ValidationError, match="at most 50 characters"):
        RegisterRequest(email="u@example.com", username="a" * 51, password="password123")


def test_username_exactly_min_length():
    r = RegisterRequest(email="u@example.com", username="abc", password="password123")
    assert r.username == "abc"


def test_username_exactly_max_length():
    r = RegisterRequest(email="u@example.com", username="a" * 50, password="password123")
    assert len(r.username) == 50


def test_password_too_short():
    with pytest.raises(ValidationError, match="at least 8 characters"):
        RegisterRequest(email="u@example.com", username="validuser", password="short")


def test_password_exactly_min_length():
    r = RegisterRequest(email="u@example.com", username="validuser", password="12345678")
    assert r.password == "12345678"


def test_invalid_email():
    with pytest.raises(ValidationError):
        RegisterRequest(email="not-an-email", username="validuser", password="password123")


def test_missing_email():
    with pytest.raises(ValidationError):
        RegisterRequest(username="validuser", password="password123")  # type: ignore[call-arg]
