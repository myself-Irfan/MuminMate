from http import HTTPStatus
from unittest.mock import Mock

import pytest
from django.test import Client
from pytest_django import Settings


def test_live_returns_ok(client: Client) -> None:
    response = client.get("/api/health/live")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_ready_returns_ok(client: Client) -> None:
    response = client.get("/api/health/ready")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_ready_returns_problem_when_db_down(
    client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("core.api.is_db_ready", Mock(return_value=False))

    response = client.get("/api/health/ready")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response["Content-Type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Service Unavailable",
        "status": HTTPStatus.SERVICE_UNAVAILABLE,
        "detail": "Database unavailable",
    }


def test_live_not_redirected_when_https(client: Client, settings: Settings) -> None:
    settings.SECURE_SSL_REDIRECT = True

    response = client.get("/api/health/live")

    assert response.status_code == HTTPStatus.OK
