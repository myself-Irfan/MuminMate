import pytest
from django.test import Client
from pytest_django import Settings

from config.env import EmailLoginLimit, LoginLimit, LoginLimits
from users.models import User


@pytest.fixture
def short_password() -> str:
    return "quiet-7"


@pytest.fixture
def other_staff_user(db: None, password: str) -> User:
    return User.objects.create_user(email="peer@example.com", password=password, is_staff=True)


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
        email_ip=LoginLimit(max_failures=2, window_seconds=60),
        ip=LoginLimit(max_failures=3, window_seconds=60),
        email=EmailLoginLimit(max_failures=4, window_seconds=300, backoff_seconds=30),
    )
    settings.LOGIN_LIMITS = limits
    return limits
