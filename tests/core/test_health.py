from http import HTTPStatus

import pytest
from django.test import Client


def test_live_returns_ok(client: Client) -> None:
    response = client.get("/api/health/live")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_ready_returns_ok(client: Client) -> None:
    response = client.get("/api/health/ready")

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"status": "ok"}


def test_ready_returns_problems_db_down(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("core.api.db_ready", lambda: False)

    response = client.get("/api/health/ready")

    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response["Content-Type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Service Unavailable",
        "status": HTTPStatus.SERVICE_UNAVAILABLE,
        "detail": "Database unavailable",
    }
