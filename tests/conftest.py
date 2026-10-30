import io
import logging.config
from collections.abc import Iterator
from unittest.mock import Mock

import pytest
from django.conf import settings as django_settings
from django.contrib.auth.models import Permission
from django.utils import timezone
from pytest_django import Settings

from config.env import LogSettings
from tests.logging_support import route_logs_to_buffer
from users.models import User


# The manifest storage needs `collectstatic`; Django's docs say tests shouldn't use it.
@pytest.fixture(autouse=True)
def plain_static_storage(settings: Settings) -> None:
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


# Every request is audited: without this, the suite fills the real broker's audit queue.
@pytest.fixture(autouse=True)
def audit_publish(monkeypatch: pytest.MonkeyPatch) -> Mock:
    delay = Mock()
    monkeypatch.setattr("audit.services.audit_queue_service.record_incoming_event.delay", delay)
    return delay


@pytest.fixture
def password() -> str:
    return "placeholder-password"


@pytest.fixture
def consumer_user(db: None, password: str) -> User:
    return User.objects.create_user(
        email="irfan@example.com", password=password, email_verified_at=timezone.now()
    )


@pytest.fixture
def unverified_consumer_user(db: None, password: str) -> User:
    return User.objects.create_user(email="unverified@example.com", password=password)


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
def restore_logging() -> Iterator[None]:
    yield
    logging.config.dictConfig(django_settings.LOGGING)


@pytest.fixture
def json_logs(restore_logging: None) -> io.StringIO:
    return route_logs_to_buffer(LogSettings(level="INFO", format="json"))
