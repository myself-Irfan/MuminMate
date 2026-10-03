from datetime import UTC, datetime

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from users.models import LoginFailure, User


def test_str_returns_email() -> None:
    user = User(email="irfan@example.com")

    assert str(user) == "irfan@example.com"


def test_is_email_verified_when_verified_at_set() -> None:
    user = User(email="irfan@example.com", email_verified_at=timezone.now())

    assert user.is_email_verified


def test_is_email_verified_false_when_verified_at_unset() -> None:
    user = User(email="irfan@example.com")

    assert not user.is_email_verified


@pytest.mark.django_db
def test_full_clean_normalizes_email() -> None:
    user = User(email="Irfan@Example.COM")

    user.full_clean(exclude=["password"])

    assert user.email == "irfan@example.com"


@pytest.mark.django_db
def test_save_fails_when_email_not_lowercase() -> None:
    user = User(email="Irfan@Example.com")

    with pytest.raises(IntegrityError, match="users_email_normalized"):
        user.save()


@pytest.mark.django_db
def test_save_fails_when_email_has_whitespace() -> None:
    user = User(email="irfan@example.com\t")

    with pytest.raises(IntegrityError, match="users_email_normalized"):
        user.save()


@pytest.mark.django_db
def test_validate_constraints_fails_when_email_not_normalized() -> None:
    user = User(email="Irfan@Example.com")

    with pytest.raises(ValidationError, match="Email must be lowercase, without spaces"):
        user.validate_constraints()


@pytest.mark.django_db
def test_save_fails_when_superuser_not_staff() -> None:
    user = User(email="root@example.com", is_superuser=True)

    with pytest.raises(IntegrityError, match="users_is_superuser_requires_staff"):
        user.save()


@pytest.mark.parametrize(
    ("flags", "privileged"),
    [
        ({}, False),
        ({"is_staff": True}, True),
        ({"is_superuser": True}, True),
    ],
    ids=["consumer", "staff", "superuser"],
)
def test_is_privileged_when_staff_or_superuser(flags: dict[str, bool], privileged: bool) -> None:
    user = User(email="irfan@example.com", **flags)

    assert user.is_privileged is privileged


def test_login_failure_str_shows_time_and_ip() -> None:
    failure = LoginFailure(ip="203.0.113.7", failed_at=datetime(2026, 10, 3, 9, 30, tzinfo=UTC))

    assert str(failure) == "Login failure at 2026-10-03 09:30:00+00:00 from 203.0.113.7"
