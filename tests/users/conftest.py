import pytest
from django.contrib.auth.models import Permission
from django.test import Client

from users.models import User


@pytest.fixture
def short_password() -> str:
    return "quiet-7"


@pytest.fixture
def staff_user(db: None, password: str) -> User:
    user = User.objects.create_user(email="staff@example.com", password=password, is_staff=True)
    user.user_permissions.set(
        Permission.objects.filter(
            content_type__app_label="users", codename__in=("add_user", "change_user")
        )
    )
    return user


@pytest.fixture
def non_staff_superuser(db: None, password: str) -> User:
    return User.objects.create_user(email="root@example.com", password=password, is_superuser=True)


@pytest.fixture
def staff_client(client: Client, staff_user: User) -> Client:
    client.force_login(staff_user)
    return client
