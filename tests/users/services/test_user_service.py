import io
from unittest.mock import Mock

import pytest
from django.db import IntegrityError

from tests.logging_support import events
from users.models import User
from users.services.user_service import UserService


@pytest.mark.django_db
def test_create_normalizes_email_and_sets_password(password: str) -> None:
    user = UserService().create(email=" Irfan@Example.com ", password=password)

    assert user.email == "irfan@example.com"
    assert user.check_password(password)
    assert not user.is_staff


@pytest.mark.django_db
def test_create_sets_unusable_password_when_none() -> None:
    user = UserService().create(email="irfan@example.com", password=None)

    assert not user.has_usable_password()


@pytest.mark.django_db
def test_create_makes_staff_when_asked(password: str) -> None:
    user = UserService().create(email="irfan@example.com", password=password, is_staff=True)

    assert user.is_staff


@pytest.mark.django_db
def test_create_fails_when_email_taken_in_other_case(password: str) -> None:
    UserService().create(email="irfan@example.com", password=password)

    with pytest.raises(IntegrityError):
        UserService().create(email="IRFAN@example.com", password=password)


def test_get_id_by_email_finds_user_in_any_case(consumer_user: User) -> None:
    assert UserService().get_id_by_email(f" {consumer_user.email.upper()} ") == consumer_user.pk


@pytest.mark.django_db
def test_get_id_by_email_returns_none_when_unknown() -> None:
    assert UserService().get_id_by_email("nobody@example.com") is None


@pytest.mark.django_db
def test_signup_creates_user_when_email_new(password: str) -> None:
    UserService().signup(email=" Irfan@Example.com ", password=password)

    assert User.objects.get(email="irfan@example.com").check_password(password)


def test_signup_keeps_existing_user_when_email_taken_in_other_case(
    consumer_user: User, password: str
) -> None:
    UserService().signup(email="IRFAN@example.com", password=password + "-new")

    assert User.objects.count() == 1
    consumer_user.refresh_from_db()
    assert consumer_user.check_password(password)


def test_signup_hashes_once_when_email_taken(
    monkeypatch: pytest.MonkeyPatch, consumer_user: User, password: str
) -> None:
    make_password = Mock()
    monkeypatch.setattr("users.services.user_service.make_password", make_password)

    UserService().signup(email=consumer_user.email, password=password)

    make_password.assert_called_once_with(password)


def test_signup_keeps_existing_user_when_email_is_staff(staff_user: User, password: str) -> None:
    UserService().signup(email=staff_user.email, password=password + "-new")

    assert User.objects.filter(email=staff_user.email).count() == 1


# Another signup commits between our lookup and our insert.
def test_signup_treats_parallel_signup_as_taken(
    monkeypatch: pytest.MonkeyPatch, consumer_user: User, password: str
) -> None:
    monkeypatch.setattr(UserService, "get_id_by_email", Mock(side_effect=[None, consumer_user.pk]))

    UserService().signup(email=consumer_user.email, password=password)

    assert User.objects.count() == 1


def test_parallel_signup_logged_as_ignored(
    monkeypatch: pytest.MonkeyPatch, json_logs: io.StringIO, consumer_user: User, password: str
) -> None:
    monkeypatch.setattr(UserService, "get_id_by_email", Mock(side_effect=[None, consumer_user.pk]))

    UserService().signup(email=consumer_user.email, password=password)

    [line] = events(json_logs, "signup_ignored")
    assert (line["reason"], line["user_id"]) == ("email_taken", consumer_user.pk)


@pytest.mark.django_db
def test_signup_raises_when_other_constraint_fails(password: str) -> None:
    with pytest.raises(IntegrityError, match="users_email_ascii"):
        UserService().signup(email="\u0131rfan@example.com", password=password)
