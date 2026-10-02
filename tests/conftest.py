import pytest
from pytest_django import Settings

from users.models import User


# The manifest storage needs `collectstatic`; Django's docs say tests shouldn't use it.
@pytest.fixture(autouse=True)
def plain_static_storage(settings: Settings) -> None:
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


@pytest.fixture
def password() -> str:
    return "placeholder-password"


@pytest.fixture
def consumer_user(db: None, password: str) -> User:
    return User.objects.create_user(email="irfan@example.com", password=password)
