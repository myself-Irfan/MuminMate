import pytest
from django.contrib.auth import authenticate
from django.db import IntegrityError

from users.models import User


@pytest.fixture
def password() -> str:
    return "correct-horse-battery-staple"


@pytest.mark.django_db
def test_create_user_normalizes_email(password: str) -> None:
    user = User.objects.create_user(email="  Irfan@Example.COM ", password=password)

    assert user.email == "irfan@example.com"


@pytest.mark.django_db
def test_create_user_normalizes_fullwidth_email(password: str) -> None:
    user = User.objects.create_user(email="\uff49rfan@example.com", password=password)

    assert user.email == "irfan@example.com"


@pytest.mark.django_db
def test_create_user_hashes_password(password: str) -> None:
    user = User.objects.create_user(email="irfan@example.com", password=password)

    assert user.password != password
    assert user.check_password(password)


@pytest.mark.django_db
def test_create_user_not_staff_or_superuser(password: str) -> None:
    user = User.objects.create_user(email="irfan@example.com", password=password)

    assert not user.is_staff
    assert not user.is_superuser


def test_create_user_fails_when_email_blank(password: str) -> None:
    with pytest.raises(ValueError, match="email"):
        User.objects.create_user(email="  ", password=password)


@pytest.mark.django_db
def test_create_user_fails_when_email_taken_in_other_case(password: str) -> None:
    User.objects.create_user(email="irfan@example.com", password=password)

    with pytest.raises(IntegrityError, match="users_email_key"):
        User.objects.create_user(email="IRFAN@example.com", password=password)


@pytest.mark.django_db
def test_create_superuser_is_staff_and_superuser(password: str) -> None:
    user = User.objects.create_superuser(email="admin@example.com", password=password)

    assert user.is_staff
    assert user.is_superuser


def test_create_superuser_fails_when_not_staff(password: str) -> None:
    with pytest.raises(ValueError, match="is_staff"):
        User.objects.create_superuser(email="admin@example.com", password=password, is_staff=False)


def test_create_superuser_fails_when_not_superuser(password: str) -> None:
    with pytest.raises(ValueError, match="is_superuser"):
        User.objects.create_superuser(
            email="admin@example.com", password=password, is_superuser=False
        )


@pytest.mark.django_db
def test_get_by_natural_key_matches_when_email_not_normalized(password: str) -> None:
    user = User.objects.create_user(email="irfan@example.com", password=password)

    found = User.objects.get_by_natural_key(" IRFAN@Example.com ")

    assert found == user


@pytest.mark.django_db
def test_authenticate_when_email_not_normalized(password: str) -> None:
    user = User.objects.create_user(email="irfan@example.com", password=password)

    authenticated = authenticate(email=" IRFAN@Example.com ", password=password)

    assert authenticated == user
