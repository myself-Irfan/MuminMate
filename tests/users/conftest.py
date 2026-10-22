import pytest
from django.test import Client
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from pytest_django import Settings

from users.limits import (
    LoginLimits,
    PasswordResetLimits,
    SignupLimits,
    VerificationEmailLimits,
)
from users.models import User
from users.tokens import EmailVerificationTokenGenerator


@pytest.fixture
def short_password() -> str:
    return "quiet-7"


@pytest.fixture
def other_staff_user(db: None, password: str) -> User:
    return User.objects.create_user(email="peer@example.com", password=password, is_staff=True)


@pytest.fixture
def invited_user(db: None) -> User:
    return User.objects.create_user(email="invited@example.com", password=None)


@pytest.fixture(params=["admin_user", "other_staff_user", "staff_user"])
def privileged_user(request: pytest.FixtureRequest) -> User:
    user: User = request.getfixturevalue(request.param)
    return user


@pytest.fixture
def staff_client(client: Client, staff_user: User) -> Client:
    client.force_login(staff_user)
    return client


# Small limits, independent of .env.
@pytest.fixture
def login_limits(settings: Settings) -> LoginLimits:
    limits = LoginLimits(
        email_ip_max_events=2,
        email_ip_window_seconds=60,
        ip_max_events=3,
        ip_window_seconds=60,
        email_max_events=4,
        email_window_seconds=300,
        email_backoff_seconds=30,
    )
    settings.THROTTLE_LIMITS = settings.THROTTLE_LIMITS.model_copy(update={"login": limits})
    return limits


# Small limits, independent of .env.
@pytest.fixture
def request_limits(settings: Settings) -> None:
    settings.THROTTLE_LIMITS = settings.THROTTLE_LIMITS.model_copy(
        update={
            "password_reset": PasswordResetLimits(
                email_max_events=3,
                email_window_seconds=3600,
                email_cooldown_seconds=60,
                ip_max_events=5,
                ip_window_seconds=1800,
            ),
            "signup": SignupLimits(ip_max_events=2, ip_window_seconds=600),
            "verification_email": VerificationEmailLimits(
                email_max_events=3, email_window_seconds=3600, email_cooldown_seconds=60
            ),
        }
    )


# The unverified consumer's email verification link.
@pytest.fixture
def uidb64(unverified_consumer_user: User) -> str:
    return urlsafe_base64_encode(force_bytes(unverified_consumer_user.pk))


@pytest.fixture
def token(unverified_consumer_user: User) -> str:
    return EmailVerificationTokenGenerator().make_token(unverified_consumer_user)
