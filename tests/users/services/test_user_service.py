import io
from unittest.mock import Mock

import pytest
from django.db import IntegrityError
from pytest_django import DjangoCaptureOnCommitCallbacks

from tests.logging_support import events
from users.exceptions import EmailTakenError
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


# Signup has no lookup: the form's check passed, then another signup committed first.
def test_signup_raises_when_email_taken_in_other_case(consumer_user: User, password: str) -> None:
    with pytest.raises(EmailTakenError):
        UserService().signup(email="IRFAN@example.com", password=password + "-new")

    assert User.objects.count() == 1
    consumer_user.refresh_from_db()
    assert consumer_user.check_password(password)


def test_signup_refusal_logged_when_email_taken(
    json_logs: io.StringIO, consumer_user: User, password: str
) -> None:
    with pytest.raises(EmailTakenError):
        UserService().signup(email=consumer_user.email, password=password)

    [line] = events(json_logs, "signup_refused")
    assert (line["reason"], line["user_id"]) == ("email_taken", consumer_user.pk)


@pytest.fixture
def signup_email_delay(monkeypatch: pytest.MonkeyPatch) -> Mock:
    delay = Mock()
    monkeypatch.setattr("users.services.user_service.send_signup_email.delay", delay)
    return delay


@pytest.mark.django_db
def test_signup_queues_signup_email_only_after_commit(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    password: str,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks:
        UserService().signup(email="new@example.com", password=password)

    assert len(callbacks) == 1
    signup_email_delay.assert_not_called()


@pytest.mark.django_db
def test_signup_queues_signup_email_for_new_user(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    signup_email_delay: Mock,
    password: str,
) -> None:
    with django_capture_on_commit_callbacks(execute=True):
        UserService().signup(email="new@example.com", password=password)

    signup_email_delay.assert_called_once_with(User.objects.get(email="new@example.com").pk)


def test_signup_queues_no_email_when_email_taken(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    consumer_user: User,
    password: str,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks, pytest.raises(EmailTakenError):
        UserService().signup(email=consumer_user.email, password=password)

    assert callbacks == []


@pytest.mark.django_db
def test_signup_raises_when_other_constraint_fails(password: str) -> None:
    with pytest.raises(IntegrityError, match="users_email_ascii"):
        UserService().signup(email="\u0131rfan@example.com", password=password)
