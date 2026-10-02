import pytest
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from users.models import User


@pytest.mark.django_db
def test_create_user_hashes_password_with_argon2id(password: str) -> None:
    user = User.objects.create_user(email="irfan@example.com", password=password)

    assert user.password.startswith("argon2$argon2id$")


@pytest.mark.django_db
def test_check_password_rejects_truncated_long_password() -> None:
    long_password = "correct-horse-battery-staple-" * 5
    user = User.objects.create_user(email="irfan@example.com", password=long_password)

    assert user.check_password(long_password)
    # bcrypt silently truncates at 72 bytes.
    assert not user.check_password(long_password[:72])


@pytest.mark.django_db
def test_check_password_is_case_sensitive(password: str) -> None:
    user = User.objects.create_user(email="irfan@example.com", password=password)

    assert user.check_password(password)
    assert not user.check_password(password.upper())


def test_validate_password_rejects_when_shorter_than_8(short_password: str) -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_password(short_password)

    assert {error.code for error in excinfo.value.error_list} == {"password_too_short"}


def test_validate_password_accepts_8_characters() -> None:
    validate_password("quiet-72")


def test_validate_password_rejects_common_password() -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_password("password")

    assert "password_too_common" in {error.code for error in excinfo.value.error_list}


def test_validate_password_rejects_when_similar_to_email() -> None:
    user = User(email="quietlantern@example.com")

    with pytest.raises(ValidationError) as excinfo:
        validate_password("quietlantern@example", user=user)

    assert {error.code for error in excinfo.value.error_list} == {"password_too_similar"}


def test_validate_password_rejects_all_digits() -> None:
    with pytest.raises(ValidationError) as excinfo:
        validate_password("804719263518")

    assert {error.code for error in excinfo.value.error_list} == {"password_entirely_numeric"}
