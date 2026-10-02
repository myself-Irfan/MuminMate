import pytest
from django.test import Client

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
