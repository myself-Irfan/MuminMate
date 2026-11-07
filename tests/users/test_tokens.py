from collections.abc import Callable
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core import signing
from django.utils import timezone
from pytest_django import Settings

from users.models import User
from users.tokens import (
    ConsumerPasswordResetTokenGenerator,
    EmailChangeSigner,
    EmailVerificationTokenGenerator,
    InviteTokenGenerator,
    LinkTokenGenerator,
)


@pytest.fixture
def generator() -> EmailVerificationTokenGenerator:
    return EmailVerificationTokenGenerator()


def make_token_aged(
    monkeypatch: pytest.MonkeyPatch, generator: LinkTokenGenerator, user: User, age_seconds: int
) -> str:
    issued_at = datetime(2026, 10, 12, 12, 0)
    monkeypatch.setattr(generator, "_now", Mock(return_value=issued_at))
    token = generator.make_token(user)
    monkeypatch.setattr(
        generator, "_now", Mock(return_value=issued_at + timedelta(seconds=age_seconds))
    )
    return token


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

    token = make_token_aged(monkeypatch, generator, consumer_user, age_seconds)

    assert generator.check_token(consumer_user, token) is valid


@pytest.mark.parametrize(("age_seconds", "valid"), [(600, True), (601, False)])
def test_consumer_password_reset_token_expires_after_reset_link_timeout(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    consumer_user: User,
    age_seconds: int,
    valid: bool,
) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 3600
    settings.PASSWORD_RESET_LINK_TIMEOUT = 600
    generator = ConsumerPasswordResetTokenGenerator()

    token = make_token_aged(monkeypatch, generator, consumer_user, age_seconds)

    assert generator.check_token(consumer_user, token) is valid


@pytest.mark.parametrize("generator_class", [EmailVerificationTokenGenerator, InviteTokenGenerator])
def test_token_outlives_reset_link_timeout(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    invited_user: User,
    generator_class: type[LinkTokenGenerator],
) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 3600
    settings.PASSWORD_RESET_LINK_TIMEOUT = 600
    generator = generator_class()

    token = make_token_aged(monkeypatch, generator, invited_user, 601)

    assert generator.check_token(invited_user, token)


@pytest.mark.parametrize(
    ("generator", "lifetime"),
    [
        (EmailVerificationTokenGenerator(), "1\xa0hour"),
        (InviteTokenGenerator(), "1\xa0hour"),
        (ConsumerPasswordResetTokenGenerator(), "10\xa0minutes"),
    ],
)
def test_describe_lifetime_states_own_timeout(
    settings: Settings, generator: LinkTokenGenerator, lifetime: str
) -> None:
    settings.PASSWORD_RESET_TIMEOUT = 3600
    settings.PASSWORD_RESET_LINK_TIMEOUT = 600

    assert generator.describe_lifetime() == lifetime


def test_consumer_password_reset_key_salt_differs_from_django() -> None:
    assert ConsumerPasswordResetTokenGenerator.key_salt != PasswordResetTokenGenerator.key_salt


def test_consumer_password_reset_token_valid_for_its_user(consumer_user: User) -> None:
    generator = ConsumerPasswordResetTokenGenerator()
    token = generator.make_token(consumer_user)

    assert generator.check_token(consumer_user, token)


@pytest.mark.parametrize(
    "change", [{"is_active": False}, {"is_staff": True}], ids=["deactivated", "made_staff"]
)
def test_consumer_password_reset_token_invalid_when_account_changed(
    consumer_user: User, change: dict[str, bool]
) -> None:
    generator = ConsumerPasswordResetTokenGenerator()
    token = generator.make_token(consumer_user)

    User.objects.filter(pk=consumer_user.pk).update(**change)
    consumer_user.refresh_from_db()

    assert not generator.check_token(consumer_user, token)


def test_invite_token_invalid_when_account_deactivated(invited_user: User) -> None:
    generator = InviteTokenGenerator()
    token = generator.make_token(invited_user)

    User.objects.filter(pk=invited_user.pk).update(is_active=False)
    invited_user.refresh_from_db()

    assert not generator.check_token(invited_user, token)


@pytest.fixture
def signer() -> EmailChangeSigner:
    return EmailChangeSigner()


def test_email_change_token_reads_back_user_and_new_email(
    signer: EmailChangeSigner, consumer_user: User
) -> None:
    token = signer.make_token(consumer_user, "a2@example.com")

    claim = signer.read_token(token)

    assert claim is not None
    assert (claim.user_id, claim.new_email) == (consumer_user.pk, "a2@example.com")
    assert signer.is_current(consumer_user, claim)


def test_email_change_token_hides_password_hash(
    signer: EmailChangeSigner, consumer_user: User
) -> None:
    token = signer.make_token(consumer_user, "a2@example.com")

    assert consumer_user.password not in str(signing.loads(token, salt=signer.salt))


def test_email_change_token_refused_when_edited(
    signer: EmailChangeSigner, consumer_user: User
) -> None:
    token = signer.make_token(consumer_user, "a2@example.com")

    assert signer.read_token(f"{token[:-1]}{'B' if token[-1] == 'A' else 'A'}") is None


def test_email_change_token_refused_when_signed_with_other_salt(
    signer: EmailChangeSigner, consumer_user: User
) -> None:
    token = signing.dumps(
        {"user_id": consumer_user.pk, "new_email": "a2@example.com", "fingerprint": ""},
        salt="other",
    )

    assert signer.read_token(token) is None


@pytest.mark.parametrize(("age_seconds", "valid"), [(600, True), (601, False)])
def test_email_change_token_expires_after_link_timeout(
    monkeypatch: pytest.MonkeyPatch,
    settings: Settings,
    signer: EmailChangeSigner,
    consumer_user: User,
    age_seconds: int,
    valid: bool,
) -> None:
    settings.EMAIL_CHANGE_LINK_TIMEOUT = 600
    issued_at = 1_800_000_000
    monkeypatch.setattr("django.core.signing.time.time", Mock(return_value=issued_at))
    token = signer.make_token(consumer_user, "a2@example.com")
    monkeypatch.setattr("django.core.signing.time.time", Mock(return_value=issued_at + age_seconds))

    assert (signer.read_token(token) is not None) is valid


@pytest.mark.parametrize(
    "change",
    [
        lambda user: user.set_password("new-placeholder-passphrase"),
        lambda user: setattr(user, "email", "a3@example.com"),
        lambda user: setattr(user, "email_verified_at", None),
    ],
    ids=["password", "email", "email_verified_at"],
)
def test_email_change_token_not_current_when_account_changed(
    signer: EmailChangeSigner, consumer_user: User, change: Callable[[User], None]
) -> None:
    claim = signer.read_token(signer.make_token(consumer_user, "a2@example.com"))
    assert claim is not None

    change(consumer_user)

    assert not signer.is_current(consumer_user, claim)


def test_email_change_signer_describes_own_timeout(settings: Settings) -> None:
    settings.EMAIL_CHANGE_LINK_TIMEOUT = 1800

    assert EmailChangeSigner().describe_lifetime() == "30\xa0minutes"
