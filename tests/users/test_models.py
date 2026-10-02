import pytest
from django.db import IntegrityError
from django.utils import timezone

from users.models import User


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
