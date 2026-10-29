from datetime import UTC, datetime

import pytest
from django.contrib.auth.hashers import UNUSABLE_PASSWORD_PREFIX
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from users.enums import ThrottleScope
from users.models import ThrottleEvent, User


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
def test_full_clean_fails_when_email_not_ascii() -> None:
    user = User(email="\u0131rfan@example.com")

    with pytest.raises(ValidationError) as error:
        user.full_clean(exclude=["password"])

    assert [e.code for e in error.value.error_dict["email"]] == ["email_not_ascii"]


@pytest.mark.django_db
def test_save_fails_when_email_not_ascii() -> None:
    user = User(email="\u0131rfan@example.com")

    with pytest.raises(IntegrityError, match="users_email_ascii"):
        user.save()


@pytest.mark.django_db
def test_save_fails_when_superuser_not_staff() -> None:
    user = User(email="root@example.com", is_superuser=True)

    with pytest.raises(IntegrityError, match="users_is_superuser_requires_staff"):
        user.save()


@pytest.mark.django_db
def test_validate_constraints_fails_when_superuser_not_staff() -> None:
    user = User(email="root@example.com", is_superuser=True)

    with pytest.raises(ValidationError, match="A superuser must also be staff"):
        user.validate_constraints()


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


@pytest.mark.parametrize(
    ("fields", "allowed"),
    [
        ({}, True),
        ({"is_active": False}, False),
        ({"is_staff": True}, False),
        ({"is_staff": True, "is_superuser": True}, False),
        ({"password": UNUSABLE_PASSWORD_PREFIX}, False),
    ],
    ids=["consumer", "inactive", "staff", "superuser", "no_password"],
)
def test_can_reset_password_when_active_consumer_with_password(
    fields: dict[str, object], allowed: bool
) -> None:
    user = User(**{"email": "irfan@example.com", "password": "argon2$hash", **fields})

    assert user.can_reset_password is allowed


@pytest.mark.parametrize(
    ("fields", "pending"),
    [
        ({}, True),
        ({"is_staff": True}, True),
        ({"is_active": False}, False),
        ({"password": "argon2$hash"}, False),
    ],
    ids=["invited", "invited_staff", "inactive", "password_set"],
)
def test_is_invite_pending_when_active_without_password(
    fields: dict[str, object], pending: bool
) -> None:
    user = User(**{"email": "invited@example.com", "password": UNUSABLE_PASSWORD_PREFIX, **fields})

    assert user.is_invite_pending is pending


@pytest.mark.parametrize(
    ("fields", "pending"),
    [
        ({}, True),
        ({"email_verified_at": timezone.now()}, False),
        ({"is_active": False}, False),
    ],
    ids=["unverified", "verified", "inactive"],
)
def test_is_verification_pending_when_active_and_unverified(
    fields: dict[str, object], pending: bool
) -> None:
    user = User(**{"email": "irfan@example.com", **fields})

    assert user.is_verification_pending is pending


def test_throttle_event_str_shows_scope_time_and_ip() -> None:
    event = ThrottleEvent(
        scope=ThrottleScope.LOGIN_FAILURE,
        ip="203.0.113.7",
        created_at=datetime(2026, 10, 3, 9, 30, tzinfo=UTC),
    )

    assert str(event) == "Login Failure at 2026-10-03 09:30:00+00:00 from 203.0.113.7"


@pytest.mark.django_db
def test_throttle_event_save_fails_when_scope_unknown() -> None:
    event = ThrottleEvent(scope="login_falure", email_digest="digest")

    with pytest.raises(IntegrityError, match="throttle_events_scope_valid"):
        event.save()
