from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils import timezone
from pytest_django import Settings

from users.models import User
from users.tokens import EmailVerificationTokenGenerator


@pytest.fixture
def generator() -> EmailVerificationTokenGenerator:
    return EmailVerificationTokenGenerator()


def test_token_valid_for_its_user(
    generator: EmailVerificationTokenGenerator, consumer_user: User
) -> None:
    token = generator.make_token(consumer_user)

    assert generator.check_token(consumer_user, token)


def test_token_invalid_for_another_user(
    generator: EmailVerificationTokenGenerator, consumer_user: User, staff_user: User
) -> None:
    token = generator.make_token(consumer_user)

    assert not generator.check_token(staff_user, token)


def test_token_invalid_once_email_verified(
    generator: EmailVerificationTokenGenerator, consumer_user: User
) -> None:
    token = generator.make_token(consumer_user)

    consumer_user.email_verified_at = timezone.now()
    consumer_user.save()

    assert not generator.check_token(consumer_user, token)


def test_token_invalid_when_email_changed(
    generator: EmailVerificationTokenGenerator, consumer_user: User
) -> None:
    token = generator.make_token(consumer_user)

    consumer_user.email = "changed@example.com"
    consumer_user.save()

    assert not generator.check_token(consumer_user, token)


def test_token_valid_after_login(
    generator: EmailVerificationTokenGenerator, consumer_user: User
) -> None:
    token = generator.make_token(consumer_user)

    consumer_user.last_login = timezone.now()
    consumer_user.save()

    assert generator.check_token(consumer_user, token)


def test_token_valid_after_password_change(
    generator: EmailVerificationTokenGenerator, consumer_user: User
) -> None:
    token = generator.make_token(consumer_user)

    consumer_user.set_password("another-placeholder-password")
    consumer_user.save()

    assert generator.check_token(consumer_user, token)


# The user-facing guarantee; holds while either the salt or the hash differs from Django's.
def test_password_reset_token_rejected(
    generator: EmailVerificationTokenGenerator, consumer_user: User
) -> None:
    reset_token = PasswordResetTokenGenerator().make_token(consumer_user)

    assert not generator.check_token(consumer_user, reset_token)


def test_key_salt_differs_from_password_reset() -> None:
    assert EmailVerificationTokenGenerator.key_salt != PasswordResetTokenGenerator.key_salt


@pytest.mark.parametrize(("age_seconds", "valid"), [(600, True), (601, False)])
def test_token_expires_after_password_reset_timeout(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    generator: EmailVerificationTokenGenerator,
    consumer_user: User,
    age_seconds: int,
    valid: bool,
) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 600
    issued_at = datetime(2026, 10, 12, 12, 0)
    monkeypatch.setattr(generator, "_now", Mock(return_value=issued_at))
    token = generator.make_token(consumer_user)

    monkeypatch.setattr(
        generator, "_now", Mock(return_value=issued_at + timedelta(seconds=age_seconds))
    )

    assert generator.check_token(consumer_user, token) is valid
