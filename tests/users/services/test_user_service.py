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


@pytest.mark.django_db
def test_signup_requests_verification_for_new_user(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    request_verification = Mock()
    monkeypatch.setattr(
        "users.services.user_service.EmailVerificationService.request_verification",
        request_verification,
    )

    UserService().signup(email="new@example.com", password=password)

    request_verification.assert_called_once_with(User.objects.get(email="new@example.com"))


def test_signup_queues_no_email_when_email_taken(
    django_capture_on_commit_callbacks: DjangoCaptureOnCommitCallbacks,
    consumer_user: User,
    password: str,
) -> None:
    with django_capture_on_commit_callbacks() as callbacks, pytest.raises(EmailTakenError):
        UserService().signup(email=consumer_user.email, password=password)

    assert callbacks == []


@pytest.mark.django_db
def test_signup_raises_when_other_integrity_error(
    monkeypatch: pytest.MonkeyPatch, password: str
) -> None:
    monkeypatch.setattr(
        "users.services.user_service.UserService.create",
        Mock(side_effect=IntegrityError("other")),
    )

    with pytest.raises(IntegrityError, match="other"):
        UserService().signup(email="new@example.com", password=password)


# Opening the link proved the new inbox is the user's.
def test_change_email_saves_normalized_email_marked_verified(
    unverified_consumer_user: User,
) -> None:
    UserService().change_email(unverified_consumer_user, " New@Example.com ")

    unverified_consumer_user.refresh_from_db()
    assert unverified_consumer_user.email == "new@example.com"
    assert unverified_consumer_user.is_email_verified


def test_change_email_updates_given_user(unverified_consumer_user: User) -> None:
    changed = UserService().change_email(unverified_consumer_user, "new@example.com")

    assert changed
    assert unverified_consumer_user.email == "new@example.com"
    assert unverified_consumer_user.is_email_verified


# Another account took the address after the link was sent.
def test_change_email_raises_when_email_taken(consumer_user: User, staff_user: User) -> None:
    with pytest.raises(EmailTakenError):
        UserService().change_email(staff_user, consumer_user.email.upper())

    assert staff_user.email == "staff@example.com"
    staff_user.refresh_from_db()
    assert staff_user.email == "staff@example.com"


# A second request loaded the user before the first one committed (a double click).
def test_change_email_changes_nothing_when_email_changed_since_loaded(
    consumer_user: User,
) -> None:
    User.objects.filter(pk=consumer_user.pk).update(email="first@example.com")

    changed = UserService().change_email(consumer_user, "second@example.com")

    assert not changed
    assert consumer_user.email == "irfan@example.com"
    consumer_user.refresh_from_db()
    assert consumer_user.email == "first@example.com"


def test_change_email_raises_when_other_integrity_error(consumer_user: User) -> None:
    with pytest.raises(IntegrityError):
        UserService().change_email(consumer_user, "\u0131@example.com")
