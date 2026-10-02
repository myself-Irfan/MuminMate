from datetime import timedelta
from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.contrib.auth import SESSION_KEY
from django.contrib.sessions.models import Session
from django.test import Client
from django.utils import timezone
from pytest_django import Settings

from users.enums import SessionKey
from users.middleware import SessionTimeoutMiddleware
from users.models import User


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> Mock:
    settings.SESSION_ABSOLUTE_AGE = 600
    clock = Mock(return_value=1_000_000.0)
    monkeypatch.setattr("users.signals.time", Mock(time=clock))
    monkeypatch.setattr("users.middleware.time", Mock(time=clock))
    return clock


def test_login_sets_login_at(client: Client, admin_user: User, clock: Mock) -> None:
    client.force_login(admin_user)

    assert client.session[SessionKey.LOGIN_AT] == 1_000_000


def test_login_resets_login_at_when_logging_in_again(
    client: Client, admin_user: User, clock: Mock
) -> None:
    client.force_login(admin_user)
    clock.return_value = 1_000_100.0

    client.force_login(admin_user)

    assert client.session[SessionKey.LOGIN_AT] == 1_000_100


def test_request_skips_session_save_within_refresh_interval(
    client: Client, admin_user: User, clock: Mock, settings: Settings
) -> None:
    client.force_login(admin_user)
    clock.return_value = 1_000_000 + SessionTimeoutMiddleware.refresh_interval_seconds - 1

    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.OK
    assert settings.SESSION_COOKIE_NAME not in response.cookies


def test_request_refreshes_session_after_refresh_interval(
    client: Client, admin_user: User, clock: Mock, settings: Settings
) -> None:
    renewed_at = 1_000_000 + SessionTimeoutMiddleware.refresh_interval_seconds
    client.force_login(admin_user)
    clock.return_value = renewed_at

    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.OK
    assert settings.SESSION_COOKIE_NAME in response.cookies
    assert client.session[SessionKey.REFRESHED_AT] == renewed_at


def test_request_refresh_extends_session_expiry(
    client: Client, admin_user: User, clock: Mock
) -> None:
    client.force_login(admin_user)
    session_key = client.session.session_key
    expiry_before = Session.objects.get(pk=session_key).expire_date
    clock.return_value = 1_000_000 + SessionTimeoutMiddleware.refresh_interval_seconds

    client.get("/admin/")

    assert Session.objects.get(pk=session_key).expire_date > expiry_before


def test_request_refreshes_at_half_idle_when_idle_shorter_than_interval(
    client: Client, admin_user: User, clock: Mock, settings: Settings
) -> None:
    settings.SESSION_COOKIE_AGE = 60
    client.force_login(admin_user)
    clock.return_value = 1_000_030.0

    client.get("/admin/")

    assert client.session[SessionKey.REFRESHED_AT] == 1_000_030


def test_request_is_anonymous_when_session_expired(
    client: Client, admin_user: User, clock: Mock
) -> None:
    client.force_login(admin_user)
    Session.objects.filter(pk=client.session.session_key).update(
        expire_date=timezone.now() - timedelta(seconds=1)
    )

    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.FOUND


def test_request_keeps_session_before_absolute_age(
    client: Client, admin_user: User, clock: Mock
) -> None:
    client.force_login(admin_user)
    clock.return_value = 1_000_599.0

    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.OK


def test_request_logs_out_at_absolute_age(client: Client, admin_user: User, clock: Mock) -> None:
    client.force_login(admin_user)
    clock.return_value = 1_000_600.0

    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.FOUND
    assert SESSION_KEY not in client.session


def test_request_logs_out_when_login_at_missing(
    client: Client, admin_user: User, clock: Mock
) -> None:
    client.force_login(admin_user)
    session = client.session
    del session[SessionKey.LOGIN_AT]
    session.save()

    response = client.get("/admin/")

    assert response.status_code == HTTPStatus.FOUND
    assert SESSION_KEY not in client.session


@pytest.mark.django_db
@pytest.mark.usefixtures("clock")
def test_anonymous_request_creates_no_session(client: Client, settings: Settings) -> None:
    response = client.get("/admin/login/")

    assert response.status_code == HTTPStatus.OK
    assert settings.SESSION_COOKIE_NAME not in response.cookies
